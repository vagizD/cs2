import sqlite3
import os
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from typing import Dict, List, Tuple

DB_PATH = "data/processed/hltv_database.db"

# Master Configuration for the 4 Case Studies
CASE_STUDIES = {
    "navi": {
        "team_id": 4608,
        "team_name": "Natus Vincere",
        "date": "2025-07-14",
        "added_name": "makazze",
        "removed_name": "jL",
        "filename": "case_study_navi.png",
        "story_title": "NAVI Post-Major Reset",
        "events": [
            {"name": "IEM Melbourne", "start_w": -11.9, "end_w": -11.7, "color": "#1F6FEB", "is_major": False, "badge_y": 91.0},
            {"name": "PGL Astana 2025", "start_w": -9.2, "end_w": -8.4, "color": "#388BFD", "is_major": False, "badge_y": 99.0},
            {"name": "BLAST.tv Austin Major", "start_w": -4.5, "end_w": -3.3, "color": "#8957E5", "is_major": True, "badge_y": 99.0},
            {"name": "IEM Cologne 2025", "start_w": 1.8, "end_w": 2.8, "color": "#1F6FEB", "is_major": False, "badge_y": 99.0},
            {"name": "Esports World Cup", "start_w": 5.2, "end_w": 5.6, "color": "#388BFD", "is_major": False, "badge_y": 91.0},
            {"name": "StarLadder Fall", "start_w": 9.5, "end_w": 10.0, "color": "#388BFD", "is_major": False, "badge_y": 91.0},
            {"name": "ESL Pro League S22", "start_w": 11.8, "end_w": 12.6, "color": "#1F6FEB", "is_major": False, "badge_y": 99.0}
        ],
        "annotations_a": [
            {"text": "Post-Major Evaluation\n(Slump triggers benching)", "xy": (-4.0, 58), "xytext": (-3.5, 28), "color": "#FFA657"},
            {"text": "Initial Adaptation\n(3/6 wins at Cologne)", "xy": (4.5, 42), "xytext": (3.5, 18), "color": "#E3B341"},
            {"text": "StarLadder Dominance\n(100% WR with makazze)", "xy": (9.4, 70), "xytext": (6.2, 70), "color": "#3FB950"}
        ],
        "annotations_b": [
            {"text": "jL Form Decline\n(Pre-move inconsistency)", "xy": (-0.5, 0.88), "xytext": (-4.5, 0.90), "color": "#FFA657"},
            {"text": "makazze Star Impact\n(1.16 average post-change)", "xy": (6.2, 1.33), "xytext": (3.5, 1.43), "color": "#3FB950"}
        ]
    },
    "mouz": {
        "team_id": 4494,
        "team_name": "MOUZ",
        "date": "2025-01-27",
        "added_name": "Spinx",
        "removed_name": "siuhy",
        "filename": "case_study_mouz.png",
        "story_title": "MOUZ Captaincy Shift",
        "events": [
            {"name": "BLAST World Final", "start_w": -12.7, "end_w": -12.4, "color": "#388BFD", "is_major": False, "badge_y": 91.0},
            {"name": "Shanghai Major RMR", "start_w": -10.1, "end_w": -10.0, "color": "#6E40C9", "is_major": False, "badge_y": 99.0},
            {"name": "Shanghai Major 2024", "start_w": -7.5, "end_w": -6.2, "color": "#8957E5", "is_major": True, "badge_y": 99.0},
            {"name": "IEM Katowice 2025", "start_w": 0.8, "end_w": 1.1, "color": "#1F6FEB", "is_major": False, "badge_y": 99.0},
            {"name": "PGL Cluj-Napoca", "start_w": 2.6, "end_w": 4.0, "color": "#388BFD", "is_major": False, "badge_y": 91.0},
            {"name": "ESL Pro League S21", "start_w": 5.7, "end_w": 7.0, "color": "#1F6FEB", "is_major": False, "badge_y": 99.0},
            {"name": "BLAST Open Lisbon", "start_w": 7.4, "end_w": 8.9, "color": "#388BFD", "is_major": False, "badge_y": 91.0},
            {"name": "IEM Melbourne 2025", "start_w": 12.0, "end_w": 12.8, "color": "#1F6FEB", "is_major": False, "badge_y": 99.0}
        ],
        "annotations_a": [
            {"text": "Winter Player Break\n(No official matches)", "xy": (-2.5, 57), "xytext": (-4.5, 30), "color": "#8B949E"},
            {"text": "Katowice Role Dip\n(0/2 opening matches)", "xy": (1.0, 5), "xytext": (3.5, 18), "color": "#E3B341"},
            {"text": "Post-Break Surge\n(71–75% WR across EPL & Cluj)", "xy": (6.3, 68.0), "xytext": (6.5, 30), "color": "#3FB950"}
        ],
        "annotations_b": [
            {"text": "siuhy Fragging Deficit\n(1.04 vs Core 1.13)", "xy": (-7.0, 1.05), "xytext": (-5.5, 0.88), "color": "#FFA657"},
            {"text": "Spinx Firepower Injection\n(Elevates core baseline to 1.13)", "xy": (4.5, 1.16), "xytext": (4.5, 1.34), "color": "#3FB950"}
        ]
    },
    "falcons": {
        "team_id": 11283,
        "team_name": "Falcons",
        "date": "2026-04-20",
        "added_name": "karrigan",
        "removed_name": "kyxsan",
        "filename": "case_study_falcons.png",
        "story_title": "Falcons Championship Blueprint",
        "events": [
            {"name": "BLAST Bounty 2026", "start_w": -12.5, "end_w": -12.1, "color": "#388BFD", "is_major": False, "badge_y": 91.0},
            {"name": "IEM Kraków 2026", "start_w": -11.1, "end_w": -10.7, "color": "#1F6FEB", "is_major": False, "badge_y": 99.0},
            {"name": "PGL Cluj-Napoca", "start_w": -9.2, "end_w": -8.4, "color": "#388BFD", "is_major": False, "badge_y": 91.0},
            {"name": "BLAST Rotterdam", "start_w": -4.7, "end_w": -3.3, "color": "#388BFD", "is_major": False, "badge_y": 99.0},
            {"name": "IEM Rio 2026", "start_w": -0.9, "end_w": -0.1, "color": "#1F6FEB", "is_major": False, "badge_y": 91.0},
            {"name": "PGL Astana 2026", "start_w": 2.8, "end_w": 3.9, "color": "#388BFD", "is_major": False, "badge_y": 91.0},
            {"name": "CS Asia Champs", "start_w": 4.3, "end_w": 4.9, "color": "#388BFD", "is_major": False, "badge_y": 99.0},
            {"name": "IEM Cologne Major [CHAMPIONS]", "start_w": 7.5, "end_w": 8.9, "color": "#8957E5", "is_major": True, "badge_y": 99.0}
        ],
        "annotations_a": [
            {"text": "Pre-Change Plateaus\n(50% win rate across Europe)", "xy": (-7.0, 50), "xytext": (-6.5, 28), "color": "#FFA657"},
            {"text": "Immediate Leadership Lift\n(71–80% WR in Asia & Astana)", "xy": (3.1, 68.0), "xytext": (0.5, 36), "color": "#58A6FF"},
            {"text": "Major Championship Run\n(6/7 wins, 3-0 Grand Final)", "xy": (7.8, 70.0), "xytext": (6.0, 36), "color": "#3FB950"}
        ],
        "annotations_b": [
            {"text": "kyxsan Fragging Gap\n(0.99 rating vs 1.20+ core)", "xy": (-4.5, 1.06), "xytext": (-8.0, 0.78), "color": "#FFA657"},
            {"text": "Superstars Unlocked\n(m0NESY & NiKo dominate at 1.25+)", "xy": (4.0, 1.23), "xytext": (4.5, 1.38), "color": "#FFB800"}
        ]
    },
    "vitality": {
        "team_id": 9565,
        "team_name": "Vitality",
        "date": "2025-01-13",
        "added_name": "ropz",
        "removed_name": "Spinx",
        "filename": "case_study_vitality.png",
        "story_title": "Vitality Dynasty",
        "events": [
            {"name": "BLAST World Final", "start_w": -10.6, "end_w": -10.2, "color": "#388BFD", "is_major": False, "badge_y": 91.0},
            {"name": "Shanghai Major RMR", "start_w": -8.1, "end_w": -7.9, "color": "#6E40C9", "is_major": False, "badge_y": 99.0},
            {"name": "Shanghai Major 2024", "start_w": -5.5, "end_w": -4.4, "color": "#8957E5", "is_major": True, "badge_y": 99.0},
            {"name": "BLAST Bounty 2025", "start_w": 1.5, "end_w": 1.9, "color": "#388BFD", "is_major": False, "badge_y": 91.0},
            {"name": "IEM Katowice [1st]", "start_w": 2.8, "end_w": 4.0, "color": "#1F6FEB", "is_major": False, "badge_y": 99.0},
            {"name": "ESL Pro League S21 [1st]", "start_w": 7.6, "end_w": 9.0, "color": "#1F6FEB", "is_major": False, "badge_y": 99.0},
            {"name": "BLAST Open Lisbon [1st]", "start_w": 9.4, "end_w": 10.9, "color": "#388BFD", "is_major": False, "badge_y": 91.0}
        ],
        "annotations_a": [
            {"text": "Post-Shanghai Overhaul\n(Trading Spinx for ropz)", "xy": (-4.5, 75), "xytext": (-3.2, 32), "color": "#FFA657"},
            {"text": "Unstoppable Dynasty Streak\n(100% WR across Katowice, EPL & Lisbon)", "xy": (7.6, 75.0), "xytext": (5.8, 36), "color": "#3FB950"}
        ],
        "annotations_b": [
            {"text": "Spinx Elite Baseline\n(Departed with strong 1.17 form)", "xy": (-5.8, 1.28), "xytext": (-5.0, 1.44), "color": "#FFA657"},
            {"text": "ropz Superstar Integration\n(1.21 rating, elevates ZywOo to 1.49)", "xy": (6.0, 1.37), "xytext": (5.5, 1.46), "color": "#3FB950"}
        ]
    }
}


def load_team_case_study_data(conn: sqlite3.Connection, cfg: Dict, window_matches: int = 10) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, float]:
    """Extracts match-by-match, tournament-by-tournament, and player-level trajectories."""
    tid = cfg["team_id"]
    t0 = pd.to_datetime(cfg["date"])
    added_name = cfg["added_name"]
    removed_name = cfg["removed_name"]

    # 1. Fetch Tier 1 matches within [-120d, +120d] for sufficient rolling warmup
    q_matches = """
        SELECT m.match_id, m.datetime_utc, m.team1_id, m.team2_id, m.team1_score, m.team2_score,
               e.name as event_name, e.event_tier
        FROM match m
        JOIN event e ON m.event_id = e.event_id
        WHERE (m.team1_id = ? OR m.team2_id = ?)
          AND m.datetime_utc >= date(?, '-120 days') AND m.datetime_utc <= date(?, '+120 days')
          AND e.event_tier = 'Tier 1'
        ORDER BY m.datetime_utc ASC
    """
    m_df = pd.read_sql_query(q_matches, conn, params=[tid, tid, cfg["date"], cfg["date"]])
    m_df["datetime_utc"] = pd.to_datetime(m_df["datetime_utc"])
    m_df["rel_days"] = (m_df["datetime_utc"] - t0).dt.total_seconds() / 86400.0
    m_df["rel_week"] = m_df["rel_days"] / 7.0
    m_df["won"] = np.where(m_df["team1_id"] == tid, m_df["team1_score"] > m_df["team2_score"], m_df["team2_score"] > m_df["team1_score"])

    # Rolling form over window_matches (default 10)
    m_df["rolling_wr"] = m_df["won"].rolling(window_matches, min_periods=3).mean() * 100.0

    # 2. Tournament aggregations
    ev_df = m_df.groupby("event_name", as_index=False).agg(
        first_w=("rel_week", "min"),
        last_w=("rel_week", "max"),
        mid_w=("rel_week", "mean"),
        matches=("won", "count"),
        wins=("won", "sum"),
        wr=("won", lambda x: x.mean() * 100.0)
    ).sort_values("first_w")

    # 3. Player map stats
    q_pstats = """
        SELECT p.match_id, p.player_id, pl.nickname, p.rating
        FROM player_map_stats p
        JOIN player pl ON p.player_id = pl.player_id
        WHERE p.team_id = ? AND p.rating IS NOT NULL
    """
    p_df = pd.read_sql_query(q_pstats, conn, params=[tid])
    mp_df = p_df.merge(m_df[["match_id", "datetime_utc", "rel_days", "rel_week", "event_name", "won"]], on="match_id")

    # Identify retained core 4
    pre_pids = set(mp_df[mp_df["rel_days"] < 0]["nickname"].unique())
    post_pids = set(mp_df[mp_df["rel_days"] >= 0]["nickname"].unique())
    core_candidates = (pre_pids.intersection(post_pids)) - {added_name, removed_name}
    core_counts = mp_df[mp_df["nickname"].isin(core_candidates)].groupby("nickname")["match_id"].count().sort_values(ascending=False)
    core_names = set(core_counts.head(4).index)

    # 4. Weekly series (-12 to +12) with 21-day trailing window
    weeks = np.arange(-12, 13)
    rows = []
    window_days = 21

    for w in weeks:
        target_day = w * 7.0
        day_start = target_day - window_days
        day_end = target_day

        w_matches = m_df[(m_df["rel_days"] >= day_start) & (m_df["rel_days"] <= day_end)]
        w_p = mp_df[(mp_df["rel_days"] >= day_start) & (mp_df["rel_days"] <= day_end)]

        wr = w_matches["won"].mean() * 100.0 if len(w_matches) > 0 else np.nan

        if len(w_p) > 0:
            team_r = w_p["rating"].mean()
            core_sub = w_p[w_p["nickname"].isin(core_names)]
            core_r = core_sub["rating"].mean() if len(core_sub) > 0 else np.nan
            in_sub = w_p[w_p["nickname"] == added_name]
            in_r = in_sub["rating"].mean() if len(in_sub) > 0 else np.nan
            out_sub = w_p[w_p["nickname"] == removed_name]
            out_r = out_sub["rating"].mean() if len(out_sub) > 0 else np.nan
        else:
            team_r = np.nan
            core_r = np.nan
            in_r = np.nan
            out_r = np.nan

        rows.append({
            "week": w,
            "matches": len(w_matches),
            "win_rate": wr,
            "team_rating": team_r,
            "core_rating": core_r,
            "incoming_rating": in_r,
            "outgoing_rating": out_r
        })

    weekly_df = pd.DataFrame(rows)

    # Compute healthy baseline (weeks -12 to -4)
    baseline_m = m_df[(m_df["rel_week"] >= -12) & (m_df["rel_week"] <= -4)]
    healthy_baseline_wr = baseline_m["won"].mean() * 100.0 if len(baseline_m) > 0 else m_df[m_df["rel_days"] < 0]["won"].mean() * 100.0

    # Smooth ratings: carry active form forward across tournament gaps
    weekly_df["team_rating_smooth"] = weekly_df["team_rating"].ffill().bfill()
    weekly_df["core_rating_smooth"] = weekly_df["core_rating"].ffill().bfill()
    weekly_df["outgoing_smooth"] = np.where(weekly_df["week"] <= 0, weekly_df["outgoing_rating"].ffill().bfill(), np.nan)
    weekly_df["incoming_smooth"] = np.where(weekly_df["week"] >= 0, weekly_df["incoming_rating"].ffill().bfill(), np.nan)

    return weekly_df, m_df, ev_df, healthy_baseline_wr


def render_team_case_study(cfg: Dict, weekly_df: pd.DataFrame, m_df: pd.DataFrame, ev_df: pd.DataFrame, baseline_wr: float, output_path: str, window_matches: int = 10):
    """Generates an individual 2-panel publication figure for a single team case study."""
    plt.style.use("dark_background")
    fig = plt.figure(figsize=(18, 12.0), dpi=180)
    gs = gridspec.GridSpec(2, 1, height_ratios=[1.08, 1.0], hspace=0.38, top=0.90, bottom=0.06)

    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[1, 0], sharex=ax1)

    weeks = weekly_df["week"]
    tname = cfg["team_name"]
    added = cfg["added_name"]
    removed = cfg["removed_name"]

    # -------------------------------------------------------------
    # SUBPLOT A: Match Win Rate Dynamics & Tournament Milestones
    # -------------------------------------------------------------
    color_wr = "#58A6FF"
    color_major = "#8957E5"

    # 1. Plot Tournament Context Spans
    for ev in cfg["events"]:
        sw = ev["start_w"]
        ew = ev["end_w"]
        if (ew - sw) < 1.0:
            mid = (sw + ew) / 2.0
            sw = mid - 0.5
            ew = mid + 0.5

        span_color = ev["color"]
        alpha = 0.20 if ev.get("is_major", False) else 0.11
        ax1.axvspan(sw, ew, color=span_color, alpha=alpha, zorder=1)
        ax2.axvspan(sw, ew, color=span_color, alpha=alpha * 0.7, zorder=1)

        # Staggered Badge Headers
        badge_y = ev.get("badge_y", 98.0)
        badge_border = "#D2A8FF" if ev.get("is_major", False) else span_color
        ax1.text(
            (sw + ew) / 2.0,
            badge_y,
            ev["name"],
            color="#F0F6FC",
            fontsize=8.2,
            fontweight="bold",
            ha="center",
            va="top",
            bbox=dict(boxstyle="round,pad=0.24", facecolor="#161B22", edgecolor=badge_border, alpha=0.95, lw=1.2),
            zorder=9
        )

    # 2. Rolling Form Line (matches)
    ax1.plot(
        m_df["rel_week"],
        m_df["rolling_wr"],
        color=color_wr,
        linewidth=2.6,
        label=f"Rolling {window_matches}-Match Form",
        zorder=5
    )

    # 3. Tournament Midpoint Win Rates (Large Points)
    # Filter events within timeline
    ev_in_range = ev_df[(ev_df["mid_w"] >= -12.5) & (ev_df["mid_w"] <= 12.5)]
    ax1.scatter(
        ev_in_range["mid_w"],
        ev_in_range["wr"],
        color="#F0F6FC",
        edgecolor=color_wr,
        s=85,
        linewidth=2.2,
        label="Tournament Win Rate",
        zorder=7
    )

    # Annotate percentage above tournament points
    for _, r in ev_in_range.iterrows():
        y_pos = min(102, r["wr"] + 4.5)
        ax1.text(
            r["mid_w"],
            y_pos,
            f"{r['wr']:.0f}%",
            color="#79C0FF",
            fontsize=8.0,
            fontweight="bold",
            ha="center",
            va="bottom",
            bbox=dict(boxstyle="round,pad=0.15", facecolor="#0D1117", edgecolor="none", alpha=0.85),
            zorder=9
        )

    # 4. Healthy Baseline Reference
    ax1.axhline(
        y=baseline_wr,
        color="#8B949E",
        linestyle=":",
        linewidth=1.6,
        alpha=0.85,
        label=f"Healthy Baseline ({baseline_wr:.1f}%)"
    )

    # 5. Vertical Roster Change Line at t=0
    ax1.axvline(x=0, color="#F85149", linestyle="--", linewidth=1.8, alpha=0.95, zorder=8)
    
    # Roster Change Box pinned cleanly at y = 9% so it NEVER collides with tournament badges!
    ax1.text(
        0.0, 9.0,
        f"Roster Change\n(+{added}  -{removed})",
        color="#F85149",
        fontsize=9.0,
        fontweight="bold",
        ha="center",
        va="bottom",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="#161B22", edgecolor="#F85149", alpha=0.95, lw=1.3),
        zorder=10
    )

    # Narrative Annotations for Subplot A
    for anno in cfg.get("annotations_a", []):
        ax1.annotate(
            anno["text"],
            xy=anno["xy"],
            xytext=anno["xytext"],
            arrowprops=dict(arrowstyle="->", color=anno["color"], lw=1.5),
            color=anno["color"],
            fontsize=8.8,
            fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.25", facecolor="#161B22", edgecolor=anno["color"], alpha=0.92),
            zorder=10
        )

    ax1.set_ylabel("Match Win Rate, %", color="#F0F6FC", fontsize=12, fontweight="bold", labelpad=8)
    ax1.set_xlabel("Weeks from Roster Change", color="#F0F6FC", fontsize=12, fontweight="bold", labelpad=8)
    ax1.set_xlim(-12.5, 12.5)
    ax1.set_xticks(np.arange(-12, 13, 2))
    ax1.tick_params(labelbottom=True, colors="#C9D1D9", labelsize=10)
    ax1.set_ylim(-2, 107)
    ax1.grid(True, linestyle=":", alpha=0.35, color="#30363D")
    ax1.legend(loc="lower left", facecolor="#161B22", edgecolor="#30363D", fontsize=9.0)
    ax1.set_title(
        "A. Win Rate Dynamics & Tournament Milestones",
        fontsize=13.0, fontweight="bold", color="#F0F6FC", pad=8
    )

    # -------------------------------------------------------------
    # SUBPLOT B: Player Performance Dynamics (Core 4 vs In/Out)
    # -------------------------------------------------------------
    color_core = "#FFB800"
    color_team = "#00D2FF"
    color_out = "#F85149"
    color_in = "#3FB950"

    # Core 4 Line
    ax2.plot(
        weeks,
        weekly_df["core_rating_smooth"],
        color=color_core,
        linewidth=2.6,
        marker="o",
        markersize=4.5,
        label="Core 4 Players (Retained)",
        zorder=5
    )

    # Overall Team Line
    ax2.plot(
        weeks,
        weekly_df["team_rating_smooth"],
        color=color_team,
        linewidth=2.2,
        linestyle="--",
        marker="s",
        markersize=4.0,
        label="Overall Team Average",
        zorder=4
    )

    # Outgoing Player Line (pre-change)
    pre_mask = weeks <= 0
    if weekly_df.loc[pre_mask, "outgoing_smooth"].notnull().any():
        ax2.plot(
            weeks[pre_mask],
            weekly_df.loc[pre_mask, "outgoing_smooth"],
            color=color_out,
            linewidth=2.2,
            linestyle="-.",
            marker="d",
            markersize=4.5,
            label=f"Outgoing: -{removed}",
            zorder=6
        )

    # Incoming Player Line (post-change)
    post_mask = weeks >= 0
    if weekly_df.loc[post_mask, "incoming_smooth"].notnull().any():
        ax2.plot(
            weeks[post_mask],
            weekly_df.loc[post_mask, "incoming_smooth"],
            color=color_in,
            linewidth=2.4,
            linestyle="-.",
            marker="^",
            markersize=5.0,
            label=f"Incoming: +{added}",
            zorder=6
        )

    # Narrative Annotations for Subplot B
    for anno in cfg.get("annotations_b", []):
        ax2.annotate(
            anno["text"],
            xy=anno["xy"],
            xytext=anno["xytext"],
            arrowprops=dict(arrowstyle="->", color=anno["color"], lw=1.5),
            color=anno["color"],
            fontsize=8.8,
            fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.25", facecolor="#161B22", edgecolor=anno["color"], alpha=0.92),
            zorder=10
        )

    ax2.axvline(x=0, color="#F85149", linestyle="--", linewidth=1.8, alpha=0.95, zorder=8)
    ax2.set_ylabel("HLTV Rating", color="#F0F6FC", fontsize=12, fontweight="bold", labelpad=8)
    ax2.set_xlabel("Weeks from Roster Change", color="#F0F6FC", fontsize=12, fontweight="bold", labelpad=8)
    ax2.set_xlim(-12.5, 12.5)
    ax2.set_xticks(np.arange(-12, 13, 2))
    ax2.tick_params(colors="#C9D1D9", labelsize=10)

    # Determine dynamic Y-limits with ample headroom for annotations
    all_ratings = pd.concat([
        weekly_df["core_rating_smooth"],
        weekly_df["team_rating_smooth"],
        weekly_df["outgoing_smooth"].dropna(),
        weekly_df["incoming_smooth"].dropna()
    ])
    y_min = max(0.68, all_ratings.min() - 0.08)
    y_max = min(1.58, all_ratings.max() + 0.16)
    ax2.set_ylim(y_min, y_max)

    ax2.grid(True, linestyle=":", alpha=0.35, color="#30363D")
    ax2.legend(loc="upper left", facecolor="#161B22", edgecolor="#30363D", fontsize=9.2)
    ax2.set_title(
        "B. Player Performance Dynamics",
        fontsize=13.0, fontweight="bold", color="#F0F6FC", pad=8
    )

    # Super Title with concise, elegant context
    fig.suptitle(
        f"{tname} (+{added}, -{removed}) / Tier 1\n"
        f"{cfg['story_title']} ({cfg['date']})",
        fontsize=12.0,
        fontweight="bold",
        color="#F0F6FC",
        y=0.98
    )

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    fig.savefig(output_path, bbox_inches="tight", facecolor="#0D1117")
    plt.close(fig)
    print(f"[Plot Saved] {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate team-specific roster change case studies.")
    parser.add_argument("--team", type=str, default="all", choices=["all", "navi", "mouz", "falcons", "vitality"], help="Target team case study")
    parser.add_argument("--window-size", type=int, default=10, help="Number of matches in rolling form window (default: 10)")
    parser.add_argument("--out-dir", type=str, default="data/visualization/roster_changes", help="Output directory")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    teams_to_run = list(CASE_STUDIES.keys()) if args.team == "all" else [args.team]

    for key in teams_to_run:
        cfg = CASE_STUDIES[key]
        print(f"\n>>> Rendering {cfg['team_name']} (+{cfg['added_name']} -{cfg['removed_name']}) with Rolling {args.window_size}-Match Form...")
        weekly_df, m_df, ev_df, baseline_wr = load_team_case_study_data(conn, cfg, window_matches=args.window_size)
        out_path = os.path.join(args.out_dir, cfg["filename"])
        render_team_case_study(cfg, weekly_df, m_df, ev_df, baseline_wr, out_path, window_matches=args.window_size)

    conn.close()
    print("\nAll case study figures generated successfully!")


if __name__ == "__main__":
    main()
