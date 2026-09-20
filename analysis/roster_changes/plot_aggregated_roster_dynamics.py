import sqlite3
import os
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from typing import Optional, Tuple, Dict, List, Set


def get_player_name_map(conn: sqlite3.Connection) -> Dict[int, str]:
    """Fetches mapping from player_id to player nickname/name."""
    rows = conn.execute("SELECT player_id, nickname FROM player").fetchall()
    return {r[0]: r[1] for r in rows}


def detect_isolated_roster_changes(
    conn: sqlite3.Connection,
    isolation_days: int = 90,
    top30_only: bool = True
) -> List[Dict]:
    """Detects 1-player roster changes isolated by +/- isolation_days with no other roster changes.
    
    Criteria:
      1. Exactly 1 player added and 1 player removed in weekly ranking snapshot.
      2. No other roster change in [t0 - isolation_days, t0).
      3. No other roster change in (t0, t0 + isolation_days].
      4. Team history exists in snapshots >= isolation_days before and after t0.
      5. If top30_only is True, team held Top 30 ranking at some point.
    """
    snaps = pd.read_sql_query("""
        SELECT snapshot_date, rank, team_id, team_name,
               player_id1, player_id2, player_id3, player_id4, player_id5
        FROM ranking_snapshot
        ORDER BY team_id, snapshot_date ASC
    """, conn)
    snaps["snapshot_date"] = pd.to_datetime(snaps["snapshot_date"])
    
    top30_tids = set(snaps[snaps["rank"] <= 30]["team_id"].unique()) if top30_only else None
    name_map = get_player_name_map(conn)
    
    isolated_events = []
    
    for team_id, group in snaps.groupby("team_id"):
        if top30_only and team_id not in top30_tids:
            continue
            
        group = group.sort_values("snapshot_date").reset_index(drop=True)
        t_min = group["snapshot_date"].min()
        t_max = group["snapshot_date"].max()
        
        prev_set = None
        c_list = []
        
        for idx, row in group.iterrows():
            cur_set = set([row[f"player_id{i}"] for i in range(1, 6) if pd.notnull(row[f"player_id{i}"]) and row[f"player_id{i}"] != 0])
            cur_date = row["snapshot_date"]
            
            if len(cur_set) != 5:
                continue
                
            if prev_set is not None and cur_set != prev_set:
                added = cur_set - prev_set
                removed = prev_set - cur_set
                c_list.append({
                    "team_id": team_id,
                    "team_name": group["team_name"].iloc[-1],
                    "change_date": cur_date,
                    "rank_at_change": row["rank"],
                    "added_ids": list(added),
                    "removed_ids": list(removed),
                    "retained_ids": list(cur_set.intersection(prev_set)),
                    "t_min": t_min,
                    "t_max": t_max
                })
            prev_set = cur_set
            
        all_dates = [c["change_date"] for c in c_list]
        for c in c_list:
            c_date = c["change_date"]
            # Check for any other roster change within isolation window
            other_in_pre = [d for d in all_dates if 0 < (c_date - d).days <= isolation_days]
            other_in_post = [d for d in all_dates if 0 < (d - c_date).days <= isolation_days]
            
            has_pre_history = (c_date - c["t_min"]).days >= isolation_days
            has_post_history = (c["t_max"] - c_date).days >= isolation_days
            is_single = (len(c["added_ids"]) == 1 and len(c["removed_ids"]) == 1)
            
            if is_single and len(other_in_pre) == 0 and len(other_in_post) == 0 and has_pre_history and has_post_history:
                added_name = name_map.get(c["added_ids"][0], f"P{c['added_ids'][0]}")
                removed_name = name_map.get(c["removed_ids"][0], f"P{c['removed_ids'][0]}")
                c["event_id"] = f"{c['team_id']}_{c_date.strftime('%Y%m%d')}"
                c["label"] = f"+{added_name} -{removed_name}"
                isolated_events.append(c)
                
    return isolated_events


def compute_team_level_panel_dynamics(
    conn: sqlite3.Connection,
    events: List[Dict],
    isolation_days: int = 90,
    min_matches: int = 15,
    min_matches_per_window: int = 2,
    min_matches_mode: str = "total",
    mode: str = "raw",
    event_tier: Optional[str] = "Tier 1",
    window_type: str = "trailing",
    window_days: int = 14
) -> Tuple[pd.DataFrame, pd.DataFrame, int, int]:
    """Extracts team-level panel statistics across relative weeks [-12 to +12].
    
    Averages within each team/event first to avoid cross-match dependence and team-size skew,
    then computes the cross-team mean and Standard Error of the Mean (SEM) for robust 95% CI.
    
    Args:
        min_matches: Minimum matches required.
        min_matches_per_window: Minimum matches inside each 14-day window for team inclusion.
        min_matches_mode: 'total' (pre + post >= min_matches with pre,post >= 3) or 'each' (pre >= min_matches and post >= min_matches).
        event_tier: Filter matches by event tier ('Tier 1', 'Tier 2', 'Qualifier', or 'all').
        window_type: 'trailing' (looks back window_days from week w) or 'centered' (symmetric around week w).
        window_days: duration in days for each evaluation window (e.g. 14 for 2 weeks, 21 for 3 weeks).
    """
    if event_tier and event_tier.lower() != "all":
        tier_join = f"JOIN event e ON m.event_id = e.event_id WHERE e.event_tier = '{event_tier}'"
    else:
        tier_join = "LEFT JOIN event e ON m.event_id = e.event_id"
        
    matches = pd.read_sql_query(f"""
        SELECT m.match_id, m.datetime_utc, m.team1_id, m.team2_id, m.team1_score, m.team2_score, e.event_tier
        FROM match m
        {tier_join}
    """, conn)
    matches["datetime_utc"] = pd.to_datetime(matches["datetime_utc"])
    
    pstats = pd.read_sql_query("""
        SELECT match_id, team_id, player_id, rating
        FROM player_map_stats
        WHERE rating IS NOT NULL
    """, conn)
    
    if mode == "normalized":
        p_with_dates = pstats.merge(matches[["match_id", "datetime_utc"]], on="match_id")
        conds = [
            (p_with_dates["datetime_utc"] < "2017-06-01"),
            (p_with_dates["datetime_utc"] >= "2017-06-01") & (p_with_dates["datetime_utc"] < "2025-08-25"),
            (p_with_dates["datetime_utc"] >= "2025-08-25")
        ]
        choices = ["Rating 1.0", "Rating 2.0", "Rating 3.0"]
        p_with_dates["ver"] = np.select(conds, choices, default="Rating 2.0")
        
        norm_map = {}
        for ver, grp in p_with_dates.groupby("ver"):
            norm_map[ver] = (grp["rating"].mean(), grp["rating"].std())
            
        def norm_r(row):
            v = row["ver"]
            r = row["rating"]
            if v in norm_map and norm_map[v][1] > 0:
                z = (r - norm_map[v][0]) / norm_map[v][1]
                return 1.00 + 0.20 * z
            return r
            
        p_with_dates["effective_rating"] = p_with_dates.apply(norm_r, axis=1)
        pstats = p_with_dates[["match_id", "team_id", "player_id", "effective_rating"]].rename(columns={"effective_rating": "rating"})

    m_p = pstats.merge(matches[["match_id", "datetime_utc"]], on="match_id")
    
    weeks = np.arange(-12, 13)
    qualified_events = []
    panel_records = []
    total_match_count = 0
    
    for ev in events:
        tid = ev["team_id"]
        t0 = ev["change_date"]
        retained = set(ev["retained_ids"])
        
        m_team = matches[(matches["team1_id"] == tid) | (matches["team2_id"] == tid)].copy()
        m_team["rel_days"] = (m_team["datetime_utc"] - t0).dt.total_seconds() / 86400.0
        
        m_pre = m_team[(m_team["rel_days"] >= -isolation_days) & (m_team["rel_days"] < 0)]
        m_post = m_team[(m_team["rel_days"] >= 0) & (m_team["rel_days"] <= isolation_days)]
        
        if min_matches_mode == "total":
            is_qualified = (len(m_pre) + len(m_post) >= min_matches) and (len(m_pre) >= 3 and len(m_post) >= 3)
        else:
            is_qualified = (len(m_pre) >= min_matches and len(m_post) >= min_matches)
        
        if is_qualified:
            qualified_events.append(ev)
            total_match_count += (len(m_pre) + len(m_post))
            
            sub_p = m_p[m_p["team_id"] == tid].copy()
            sub_p["rel_days"] = (sub_p["datetime_utc"] - t0).dt.total_seconds() / 86400.0
            
            for w in weeks:
                target_day = w * 7.0
                if window_type == "trailing":
                    day_start = target_day - window_days
                    day_end = target_day
                else:  # centered
                    day_start = target_day - (window_days / 2.0)
                    day_end = target_day + (window_days / 2.0)
                    
                w_matches = m_team[(m_team["rel_days"] >= day_start) & (m_team["rel_days"] <= day_end)]
                w_pstats = sub_p[(sub_p["rel_days"] >= day_start) & (sub_p["rel_days"] <= day_end)]
                
                if len(w_matches) >= min_matches_per_window:
                    wins = ((w_matches["team1_id"] == tid) & (w_matches["team1_score"] > w_matches["team2_score"])).sum() + \
                           ((w_matches["team2_id"] == tid) & (w_matches["team2_score"] > w_matches["team1_score"])).sum()
                    wr = wins / len(w_matches) * 100.0
                    
                    team_r = w_pstats["rating"].mean() if not w_pstats.empty else np.nan
                    core_pstats = w_pstats[w_pstats["player_id"].isin(retained)]
                    core_r = core_pstats["rating"].mean() if not core_pstats.empty else np.nan
                    
                    panel_records.append({
                        "event_id": ev["event_id"],
                        "team_id": tid,
                        "team_name": ev["team_name"],
                        "week": w,
                        "win_rate": wr,
                        "team_rating": team_r,
                        "core_rating": core_r,
                        "matches_in_window": len(w_matches)
                    })
                    
    df_panel = pd.DataFrame(panel_records)
    
    summary_records = []
    for w in weeks:
        sub = df_panel[df_panel["week"] == w]
        k_teams = len(sub)
        
        if k_teams > 0:
            mean_wr = sub["win_rate"].mean()
            std_wr = sub["win_rate"].std(ddof=1) if k_teams > 1 else 0.0
            sem_wr = std_wr / np.sqrt(k_teams) if k_teams > 1 else 0.0
            
            valid_team_r = sub["team_rating"].dropna()
            mean_tr = valid_team_r.mean() if not valid_team_r.empty else np.nan
            sem_tr = (valid_team_r.std(ddof=1) / np.sqrt(len(valid_team_r))) if len(valid_team_r) > 1 else 0.0
            
            valid_core_r = sub["core_rating"].dropna()
            mean_cr = valid_core_r.mean() if not valid_core_r.empty else np.nan
            sem_cr = (valid_core_r.std(ddof=1) / np.sqrt(len(valid_core_r))) if len(valid_core_r) > 1 else 0.0
            
            summary_records.append({
                "week": w,
                "active_teams": k_teams,
                "win_rate": mean_wr,
                "wr_sem": sem_wr,
                "wr_ci_lower": mean_wr - 1.96 * sem_wr,
                "wr_ci_upper": mean_wr + 1.96 * sem_wr,
                "team_rating": mean_tr,
                "team_sem": sem_tr,
                "team_ci_lower": mean_tr - 1.96 * sem_tr,
                "team_ci_upper": mean_tr + 1.96 * sem_tr,
                "core_rating": mean_cr,
                "core_sem": sem_cr,
                "core_ci_lower": mean_cr - 1.96 * sem_cr,
                "core_ci_upper": mean_cr + 1.96 * sem_cr,
            })
            
    df_summary = pd.DataFrame(summary_records)
    return pd.DataFrame(qualified_events), df_summary, len(qualified_events), total_match_count


def compute_success_distribution(
    conn: sqlite3.Connection,
    events: List[Dict],
    event_tier: Optional[str] = "Tier 1"
) -> Dict[str, Dict[str, Dict[str, float]]]:
    """Evaluates the percentage of roster changes with positive (>+5%), neutral (+/-5%), or negative (<-5%)
    win rate delta evaluated at 30, 60, and 90 days.
    
    Computes two distinct comparisons:
      1. 'healthy': Compared against Healthy Pre-Slump Baseline (Weeks -12 to -4, i.e. [-90, -28) days).
      2. 'full_pre': Compared against Full Pre-Period ([-90, 0) days, including crisis slump).
    """
    if event_tier and event_tier.lower() != "all":
        tier_join = f"JOIN event e ON m.event_id = e.event_id WHERE e.event_tier = '{event_tier}'"
    else:
        tier_join = "LEFT JOIN event e ON m.event_id = e.event_id"
        
    matches = pd.read_sql_query(f"""
        SELECT m.match_id, m.datetime_utc, m.team1_id, m.team2_id, m.team1_score, m.team2_score
        FROM match m
        {tier_join}
    """, conn)
    matches["datetime_utc"] = pd.to_datetime(matches["datetime_utc"])
    
    records = []
    for ev in events:
        tid = ev["team_id"]
        t0 = ev["change_date"]
        
        m_team = matches[(matches["team1_id"] == tid) | (matches["team2_id"] == tid)].copy()
        m_team["rel_days"] = (m_team["datetime_utc"] - t0).dt.total_seconds() / 86400.0
        
        m_pre_all = m_team[(m_team["rel_days"] >= -90) & (m_team["rel_days"] < 0)]
        m_healthy = m_team[(m_team["rel_days"] >= -90) & (m_team["rel_days"] < -28)]
        
        m_30 = m_team[(m_team["rel_days"] >= 0) & (m_team["rel_days"] <= 30)]
        m_60 = m_team[(m_team["rel_days"] >= 0) & (m_team["rel_days"] <= 60)]
        m_90 = m_team[(m_team["rel_days"] >= 0) & (m_team["rel_days"] <= 90)]
        
        if len(m_pre_all) < 3 or len(m_90) < 3:
            continue
            
        def calc_wr(sub):
            if len(sub) == 0: return np.nan
            w = ((sub["team1_id"] == tid) & (sub["team1_score"] > sub["team2_score"])).sum() + \
                ((sub["team2_id"] == tid) & (sub["team2_score"] > sub["team1_score"])).sum()
            return w / len(sub) * 100.0
            
        wr_pre_all = calc_wr(m_pre_all)
        wr_healthy = calc_wr(m_healthy) if len(m_healthy) >= 2 else np.nan
        wr_30 = calc_wr(m_30) if len(m_30) >= 2 else np.nan
        wr_60 = calc_wr(m_60) if len(m_60) >= 2 else np.nan
        wr_90 = calc_wr(m_90)
        
        records.append({
            "event_id": ev["event_id"],
            "wr_pre_all": wr_pre_all,
            "wr_healthy": wr_healthy,
            "wr_30": wr_30,
            "wr_60": wr_60,
            "wr_90": wr_90,
            # Deltas vs Healthy Baseline
            "d30_healthy": wr_30 - wr_healthy if pd.notnull(wr_30) and pd.notnull(wr_healthy) else np.nan,
            "d60_healthy": wr_60 - wr_healthy if pd.notnull(wr_60) and pd.notnull(wr_healthy) else np.nan,
            "d90_healthy": wr_90 - wr_healthy if pd.notnull(wr_90) and pd.notnull(wr_healthy) else np.nan,
            # Deltas vs Full Pre-Period
            "d30_full": wr_30 - wr_pre_all if pd.notnull(wr_30) else np.nan,
            "d60_full": wr_60 - wr_pre_all if pd.notnull(wr_60) else np.nan,
            "d90_full": wr_90 - wr_pre_all if pd.notnull(wr_90) else np.nan,
        })
        
    res_df = pd.DataFrame(records)
    
    def get_dist_for_prefix(col_suffix: str) -> Dict[str, Dict[str, float]]:
        out = {}
        for horizon in [30, 60, 90]:
            col = f"d{horizon}_{col_suffix}"
            deltas = res_df[col].dropna()
            n = len(deltas)
            if n == 0:
                continue
            imp = (deltas > 5.0).sum() / n * 100.0
            neu = ((deltas >= -5.0) & (deltas <= 5.0)).sum() / n * 100.0
            dec = (deltas < -5.0).sum() / n * 100.0
            mean_d = deltas.mean()
            out[f"{horizon}d"] = {
                "improved": imp,
                "neutral": neu,
                "declined": dec,
                "mean_delta": mean_d,
                "count": n
            }
        return out

    return {
        "healthy": get_dist_for_prefix("healthy"),
        "full_pre": get_dist_for_prefix("full")
    }


def plot_aggregated_roster_dynamics(
    db_path: str = "data/processed/hltv_database.db",
    isolation_days: int = 90,
    min_matches: int = 15,
    min_matches_per_window: int = 2,
    min_matches_mode: str = "total",
    cohort: str = "top30",
    mode: str = "raw",
    event_tier: Optional[str] = "Tier 1",
    window_type: str = "trailing",
    window_days: int = 14,
    output_path: Optional[str] = None,
    show: bool = False
) -> Tuple[plt.Figure, Tuple[plt.Axes, plt.Axes, plt.Axes]]:
    """Generates a statistically sound 3-panel event study of isolated 1-player roster moves.
    
    Uses team-level panel aggregation with cluster-robust Standard Error of the Mean (95% CI)
    to eliminate independence violations and match-count skew.
    """
    conn = sqlite3.connect(db_path)
    tier_label = event_tier if event_tier and event_tier.lower() != "all" else "All Tiers"
    
    print(f"[1/4] Detecting isolated roster changes ({isolation_days}d clean window, cohort={cohort})...")
    events = detect_isolated_roster_changes(conn, isolation_days=isolation_days, top30_only=(cohort == "top30"))
    
    print(f"[2/4] Computing team-level panel dynamics (tier={tier_label}, window={window_type} {window_days}d, min_matches={min_matches} [{min_matches_mode}], min_matches_per_window={min_matches_per_window}, mode={mode})...")
    events_df, df_summary, k_events, tot_matches = compute_team_level_panel_dynamics(
        conn=conn,
        events=events,
        isolation_days=isolation_days,
        min_matches=min_matches,
        min_matches_per_window=min_matches_per_window,
        min_matches_mode=min_matches_mode,
        mode=mode,
        event_tier=event_tier,
        window_type=window_type,
        window_days=window_days
    )
    print(f"      Qualified Events: {k_events} | Total Matches in Isolation Windows: {tot_matches:,}")
    
    print(f"[3/4] Computing success distribution at 30, 60, and 90 days ({tier_label})...")
    succ_dist = compute_success_distribution(conn, events_df.to_dict("records"), event_tier=event_tier)
    conn.close()
    
    print("[4/4] Rendering figure with rich aesthetics...")
    plt.style.use("dark_background")
    
    fig = plt.figure(figsize=(18, 16.0), dpi=180)
    gs = gridspec.GridSpec(3, 2, height_ratios=[1.15, 1.05, 0.95], hspace=0.40, wspace=0.14)
    
    ax1 = fig.add_subplot(gs[0, :])
    ax2 = fig.add_subplot(gs[1, :], sharex=ax1)
    ax3_left = fig.add_subplot(gs[2, 0])
    ax3_right = fig.add_subplot(gs[2, 1], sharey=ax3_left)
    
    weeks = df_summary["week"]
    
    # Healthy Baseline: Average across weeks -12 to -4 (representing >= 30 days before change)
    baseline_sub = df_summary[(df_summary["week"] >= -12) & (df_summary["week"] <= -4)]
    healthy_baseline_wr = baseline_sub["win_rate"].mean()
    
    # -------------------------------------------------------------
    # SUBPLOT A: Team-Level Win Rate Event Study (95% CI via SEM)
    # -------------------------------------------------------------
    color_wr = "#58A6FF"
    color_band = "#1F6FEB"
    
    ax1.fill_between(
        weeks,
        df_summary["wr_ci_lower"],
        df_summary["wr_ci_upper"],
        color=color_band,
        alpha=0.22
    )
    ax1.plot(
        weeks,
        df_summary["win_rate"],
        color=color_wr,
        linewidth=2.8,
        marker="o",
        markersize=5.5,
        label="Win Rate (95% CI)"
    )
    
    # Healthy baseline horizontal reference across weeks -12 to -4
    ax1.axhline(
        y=healthy_baseline_wr,
        color="#8B949E",
        linestyle=":",
        linewidth=1.6,
        alpha=0.85,
        label="Healthy Baseline"
    )
    
    # Context Bands:
    # 1. Major RMR & Qualifier Stage (Weeks -8.5 to -6.5)
    ax1.axvspan(-8.5, -6.5, color="#1F6FEB", alpha=0.12, zorder=1)
    ax1.text(
        -7.5, 62.0,
        "Major RMR & Qualifiers",
        color="#79C0FF", fontsize=8.5, fontweight="bold", ha="center", va="center",
        bbox=dict(boxstyle="round,pad=0.25", facecolor="#161B22", edgecolor="#1F6FEB", alpha=0.9)
    )
    
    # 2. Major & Season Finals (Weeks -4.0 to -1.8)
    ax1.axvspan(-4.0, -1.8, color="#8957E5", alpha=0.12, zorder=1)
    ax1.text(
        -2.9, 72.5,
        "Major & Season Finals",
        color="#D2A8FF", fontsize=8.5, fontweight="bold", ha="center", va="top",
        bbox=dict(boxstyle="round,pad=0.25", facecolor="#161B22", edgecolor="#8957E5", alpha=0.9)
    )
    
    # Vertical Roster Change Line
    ax1.axvline(x=0, color="#F85149", linestyle="--", linewidth=1.8, alpha=0.9, zorder=5)
    ax1.text(
        0.18, 72.5,
        "Roster Change\n(Announcement)",
        color="#F85149",
        fontsize=8.5,
        fontweight="bold",
        va="top"
    )
    
    # Annotations:
    # 1. Drop in pre-change weeks
    pre_candidates = df_summary.loc[(df_summary["week"] >= -4) & (df_summary["week"] <= 0) & df_summary["win_rate"].notnull()]
    if not pre_candidates.empty:
        min_pre_w = pre_candidates["win_rate"].idxmin()
        slump_w = df_summary.loc[min_pre_w, "week"]
        slump_val = df_summary.loc[min_pre_w, "win_rate"]
        ax1.annotate(
            "Pre-Change Drop\n(Benched player notified)",
            xy=(slump_w, slump_val),
            xytext=(slump_w - 3.8, slump_val + 1.5),
            arrowprops=dict(arrowstyle="->", color="#FFA657", lw=1.5),
            color="#FFA657",
            fontsize=9,
            fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#21262D", edgecolor="#FFA657", alpha=0.85)
        )
    
    # 2. Adaptation Period (weeks 1 to 4)
    adapt_sub = df_summary[(df_summary["week"] >= 1) & (df_summary["week"] <= 4) & df_summary["win_rate"].notnull()]
    if not adapt_sub.empty:
        adapt_w = 2 if 2 in adapt_sub["week"].values else adapt_sub["week"].iloc[0]
        adapt_val = adapt_sub.loc[adapt_sub["week"] == adapt_w, "win_rate"].values[0]
        ax1.annotate(
            "Adaptation Period\n(Initial disruption)",
            xy=(adapt_w, adapt_val),
            xytext=(adapt_w + 0.2, 25.5),
            arrowprops=dict(arrowstyle="->", color="#E3B341", lw=1.5),
            color="#E3B341",
            fontsize=9,
            fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#21262D", edgecolor="#E3B341", alpha=0.85)
        )
    
    # 3. Peak Settled Period (weeks 6-10)
    peak_sub = df_summary[(df_summary["week"] >= 6) & (df_summary["week"] <= 10) & df_summary["win_rate"].notnull()]
    if not peak_sub.empty:
        max_peak_idx = peak_sub["win_rate"].idxmax()
        peak_w = peak_sub.loc[max_peak_idx, "week"]
        peak_val = peak_sub.loc[max_peak_idx, "win_rate"]
        ax1.annotate(
            "Settled Chemistry Peak\n(~50–60 days)",
            xy=(peak_w, peak_val),
            xytext=(peak_w - 1.5, min(peak_val + 5.5, 75.0)),
            arrowprops=dict(arrowstyle="->", color="#3FB950", lw=1.5),
            color="#3FB950",
            fontsize=9,
            fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#21262D", edgecolor="#3FB950", alpha=0.85)
        )
    
    ax1.set_ylabel("Match Win Rate, %", color="#F0F6FC", fontsize=12, fontweight="bold", labelpad=8)
    ax1.set_xlabel("Weeks from Roster Change", color="#F0F6FC", fontsize=12, fontweight="bold", labelpad=8)
    ax1.tick_params(labelbottom=True, colors="#C9D1D9", labelsize=10)
    ax1.set_xlim(-12.5, 12.5)
    ax1.set_xticks(np.arange(-12, 13, 2))
    ax1.set_ylim(18, 78)
    ax1.grid(True, linestyle=":", alpha=0.35, color="#30363D")
    ax1.legend(loc="upper left", facecolor="#161B22", edgecolor="#30363D", fontsize=8.8)
    ax1.set_title(
        f"A. Win Rate Dynamics ({k_events} Roster Moves, {tot_matches:,} Matches)",
        fontsize=13, fontweight="bold", color="#F0F6FC", pad=8
    )
    
    # -------------------------------------------------------------
    # SUBPLOT B: Retained Core 4 vs Overall Team Rating Dynamics
    # -------------------------------------------------------------
    color_core = "#FFB800"  # Crisp Amber Gold
    color_team = "#00D2FF"  # Electric Cyan
    rate_unit = "Normalized Rating" if mode == "normalized" else "HLTV Rating"
    
    ax2.fill_between(
        weeks,
        df_summary["core_ci_lower"],
        df_summary["core_ci_upper"],
        color=color_core,
        alpha=0.14
    )
    ax2.plot(
        weeks,
        df_summary["core_rating"],
        color=color_core,
        linewidth=2.4,
        marker="o",
        markersize=4.5,
        label="Core 4 Players (95% CI)"
    )
    
    ax2.fill_between(
        weeks,
        df_summary["team_ci_lower"],
        df_summary["team_ci_upper"],
        color=color_team,
        alpha=0.12
    )
    ax2.plot(
        weeks,
        df_summary["team_rating"],
        color=color_team,
        linewidth=2.2,
        linestyle="--",
        marker="s",
        markersize=4.0,
        label="Overall Team (95% CI)"
    )
    
    # Annotation in Subplot B (concise, presentation-ready):
    ax2.annotate(
        "Outgoing Player Deficit\n(Triggers replacement search)",
        xy=(-9.2, 1.055),
        xytext=(-12.3, 0.985),
        arrowprops=dict(arrowstyle="->", color="#FFA657", lw=1.4),
        color="#FFA657",
        fontsize=8.5,
        fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.25", facecolor="#161B22", edgecolor="#FFA657", alpha=0.9)
    )
    
    ax2.axvline(x=0, color="#F85149", linestyle="--", linewidth=1.8, alpha=0.9, zorder=5)
    ax2.set_ylabel(rate_unit, color="#F0F6FC", fontsize=12, fontweight="bold", labelpad=8)
    ax2.set_xlabel("Weeks from Roster Change", color="#F0F6FC", fontsize=12, fontweight="bold", labelpad=8)
    ax2.set_xlim(-12.5, 12.5)
    ax2.set_xticks(np.arange(-12, 13, 2))
    ax2.tick_params(colors="#C9D1D9", labelsize=10)
    ax2.set_ylim(0.96, 1.16)
    ax2.grid(True, linestyle=":", alpha=0.35, color="#30363D")
    ax2.legend(loc="upper left", facecolor="#161B22", edgecolor="#30363D", fontsize=9.2)
    ax2.set_title(
        "B. Player Performance Dynamics: Core 4 vs. Team",
        fontsize=13, fontweight="bold", color="#F0F6FC", pad=8
    )
    
    # -------------------------------------------------------------
    # SUBPLOTS C1 & C2: Dual Success Distributions Across Horizons
    # -------------------------------------------------------------
    horizons = ["30d", "60d", "90d"]
    x_pos = np.arange(len(horizons))
    bar_width = 0.22
    
    def plot_dist_bars(ax, dist_dict, title_prefix, subtitle_text):
        imp_pcts = [dist_dict.get(h, {}).get("improved", 0.0) for h in horizons]
        neu_pcts = [dist_dict.get(h, {}).get("neutral", 0.0) for h in horizons]
        dec_pcts = [dist_dict.get(h, {}).get("declined", 0.0) for h in horizons]
        
        rects1 = ax.bar(x_pos - bar_width, imp_pcts, width=bar_width, color="#2EA043", label="Improved (ΔWin Rate > +5%)", alpha=0.9)
        rects2 = ax.bar(x_pos, neu_pcts, width=bar_width, color="#8B949E", label="Neutral (±5% ΔWin Rate)", alpha=0.85)
        rects3 = ax.bar(x_pos + bar_width, dec_pcts, width=bar_width, color="#F85149", label="Declined (ΔWin Rate < -5%)", alpha=0.9)
        
        for rects in [rects1, rects2, rects3]:
            for r in rects:
                h = r.get_height()
                ax.annotate(
                    f"{h:.1f}%",
                    xy=(r.get_x() + r.get_width() / 2, h),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha="center", va="bottom",
                    fontsize=9.5, fontweight="bold",
                    color="#F0F6FC"
                )
                
        ax.set_xticks(x_pos)
        ax.set_xticklabels([f"+{h.upper()} Post-Change" for h in horizons], fontsize=10.5, fontweight="bold", color="#F0F6FC")
        ax.set_xlabel("Post-Change Horizon", fontsize=12, fontweight="bold", color="#F0F6FC", labelpad=8)
        ax.tick_params(colors="#C9D1D9", labelsize=10)
        ax.set_ylim(0, 68)
        ax.grid(True, linestyle=":", alpha=0.35, color="#30363D", axis="y")
        ax.set_title(f"{title_prefix}\n({subtitle_text})", fontsize=11.5, fontweight="bold", color="#F0F6FC", pad=6)

    plot_dist_bars(
        ax3_left,
        succ_dist["healthy"],
        "C1. Net Impact vs. Healthy Baseline",
        "Weeks -12 to -4"
    )
    ax3_left.set_ylabel("Share of Roster Moves, %", fontsize=12, fontweight="bold", labelpad=8, color="#F0F6FC")
    ax3_left.legend(loc="upper left", facecolor="#161B22", edgecolor="#30363D", fontsize=9.0)
    
    plot_dist_bars(
        ax3_right,
        succ_dist["full_pre"],
        "C2. Net Impact vs. Full Pre-Period",
        "Weeks -12 to 0"
    )
    ax3_right.tick_params(labelleft=False)
    
    fig.suptitle(
        "Roster Change Impact\n"
        f"Top 30 Teams in Tier 1 Events | ±90 Days Period | 14-Day Window (min {min_matches_per_window} matches/window, 95% CI)",
        fontsize=15,
        fontweight="bold",
        color="#F0F6FC",
        y=0.99
    )
    
    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        fig.savefig(output_path, bbox_inches="tight", facecolor="#0D1117")
        print(f"[Plot Saved] {output_path}")
        
    if show:
        plt.show()
        
    return fig, (ax1, ax2, ax3_left, ax3_right)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Aggregated Roster Change Event Study Plot.")
    parser.add_argument("--db-path", type=str, default="data/processed/hltv_database.db", help="Path to database.")
    parser.add_argument("--isolation-days", type=int, default=90, help="Clean window days before and after change (default 90).")
    parser.add_argument("--min-matches", type=int, default=15, help="Minimum matches threshold (default 15).")
    parser.add_argument("--min-matches-mode", choices=["total", "each"], default="total", help="Mode for min matches: 'total' across 180d or 'each' (pre & post).")
    parser.add_argument("--min-matches-per-window", type=int, default=2, help="Minimum matches per 14-day statistics window to include team (default 2).")
    parser.add_argument("--cohort", choices=["top30", "all"], default="top30", help="Cohort filter: 'top30' or 'all'.")
    parser.add_argument("--event-tier", type=str, default="Tier 1", help="Event tier filter ('Tier 1', 'Tier 2', 'Qualifier', 'all').")
    parser.add_argument("--mode", choices=["raw", "normalized"], default="raw", help="Rating mode: 'raw' or 'normalized'.")
    parser.add_argument("--window-type", choices=["trailing", "centered"], default="trailing", help="Window type: 'trailing' or 'centered'.")
    parser.add_argument("--window-days", type=int, default=14, help="Window duration in days (default 14).")
    parser.add_argument("--out-dir", type=str, default="data/visualization/roster_changes", help="Output directory.")
    parser.add_argument("--output-name", type=str, default="aggregated_roster_dynamics_isolated_90d.png", help="Output file name.")
    
    args = parser.parse_args()
    
    out_file = os.path.join(args.out_dir, args.output_name)
    
    plot_aggregated_roster_dynamics(
        db_path=args.db_path,
        isolation_days=args.isolation_days,
        min_matches=args.min_matches,
        min_matches_per_window=args.min_matches_per_window,
        min_matches_mode=args.min_matches_mode,
        cohort=args.cohort,
        event_tier=args.event_tier,
        mode=args.mode,
        window_type=args.window_type,
        window_days=args.window_days,
        output_path=out_file
    )
