import sqlite3
import os
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Optional, Tuple

try:
    from adjustText import adjust_text
    HAS_ADJUST_TEXT = True
except ImportError:
    HAS_ADJUST_TEXT = False


def resolve_date_bounds(
    conn: sqlite3.Connection,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    months: Optional[int] = None
) -> Tuple[pd.Timestamp, pd.Timestamp, str]:
    """Resolves the start and end dates for filtering matches."""
    row = conn.execute("SELECT MIN(datetime_utc), MAX(datetime_utc) FROM match").fetchone()
    min_db_str, max_db_str = row[0], row[1]
    
    db_min = pd.to_datetime(min_db_str) if min_db_str else pd.to_datetime("2020-01-01")
    db_max = pd.to_datetime(max_db_str) if max_db_str else pd.to_datetime("2026-12-31")

    dt_end = pd.to_datetime(end_date) if end_date else db_max

    if start_date:
        dt_start = pd.to_datetime(start_date)
        label = f"Window: {dt_start.strftime('%Y-%m-%d')} to {dt_end.strftime('%Y-%m-%d')}"
    elif months:
        dt_start = dt_end - pd.DateOffset(months=months)
        label = f"Window: Last {months} Months ({dt_start.strftime('%Y-%m-%d')} to {dt_end.strftime('%Y-%m-%d')})"
    else:
        dt_start = db_min
        label = f"Window: Full Dataset ({dt_start.strftime('%Y-%m-%d')} to {dt_end.strftime('%Y-%m-%d')})"

    return dt_start, dt_end, label


def load_tier1_team_performance(
    db_path: str = "data/processed/hltv_database.db",
    mode: str = "normalized",
    min_matches: int = 10,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    months: Optional[int] = None
) -> Tuple[pd.DataFrame, str]:
    """Loads and computes Tier 1 match win rates and average player ratings for Top 30 teams."""
    if mode not in ("raw", "normalized"):
        raise ValueError(f"Invalid mode '{mode}'. Must be 'raw' or 'normalized'.")

    conn = sqlite3.connect(db_path)
    dt_start, dt_end, window_label = resolve_date_bounds(conn, start_date, end_date, months)

    latest_date = conn.execute("SELECT MAX(snapshot_date) FROM ranking_snapshot").fetchone()[0]
    top30_teams = pd.read_sql_query("""
        SELECT rank, team_id, team_name, points
        FROM ranking_snapshot
        WHERE snapshot_date = ? AND rank <= 30
        ORDER BY rank ASC
    """, conn, params=[latest_date])

    top30_ids = tuple(top30_teams["team_id"].tolist())

    t1_matches = pd.read_sql_query(f"""
        SELECT 
            m.match_id,
            m.datetime_utc,
            m.team1_id,
            m.team1_name,
            m.team2_id,
            m.team2_name,
            m.team1_score,
            m.team2_score
        FROM match m
        JOIN event e ON m.event_id = e.event_id
        WHERE e.event_tier = 'Tier 1'
          AND (m.team1_id IN {top30_ids} OR m.team2_id IN {top30_ids})
          AND m.datetime_utc >= ?
          AND m.datetime_utc <= ?
    """, conn, params=[dt_start.strftime("%Y-%m-%d %H:%M:%S"), dt_end.strftime("%Y-%m-%d %H:%M:%S")])
    t1_matches["datetime_utc"] = pd.to_datetime(t1_matches["datetime_utc"])

    pstats = pd.read_sql_query(f"""
        SELECT 
            p.map_stats_id,
            p.match_id,
            p.team_id,
            p.player_id,
            p.player_name,
            p.rating,
            m.datetime_utc
        FROM player_map_stats p
        JOIN match m ON p.match_id = m.match_id
        JOIN event e ON m.event_id = e.event_id
        WHERE e.event_tier = 'Tier 1'
          AND p.team_id IN {top30_ids}
          AND m.datetime_utc >= ?
          AND m.datetime_utc <= ?
    """, conn, params=[dt_start.strftime("%Y-%m-%d %H:%M:%S"), dt_end.strftime("%Y-%m-%d %H:%M:%S")])
    pstats["datetime_utc"] = pd.to_datetime(pstats["datetime_utc"])

    conditions = [
        (pstats["datetime_utc"] < "2017-06-01"),
        (pstats["datetime_utc"] >= "2017-06-01") & (pstats["datetime_utc"] < "2025-08-25"),
        (pstats["datetime_utc"] >= "2025-08-25")
    ]
    choices = ["Rating 1.0", "Rating 2.0", "Rating 3.0"]
    pstats["rating_version"] = np.select(conditions, choices, default="Rating 2.0")

    if mode == "normalized":
        version_stats = {}
        for ver, group in pstats.groupby("rating_version"):
            mean_r = group["rating"].mean()
            std_r = group["rating"].std()
            version_stats[ver] = (mean_r, std_r)

        def normalize_rating(row):
            r = row["rating"]
            ver = row["rating_version"]
            if pd.isnull(r) or ver not in version_stats:
                return r
            mu, sigma = version_stats[ver]
            if sigma == 0:
                return r
            z = (r - mu) / sigma
            return 1.00 + 0.20 * z

        pstats["effective_rating"] = pstats.apply(normalize_rating, axis=1)
    else:
        pstats["effective_rating"] = pstats["rating"]

    team_records = []
    for idx, row in top30_teams.iterrows():
        tid = row["team_id"]
        tname = row["team_name"]

        m1 = t1_matches[t1_matches["team1_id"] == tid]
        m2 = t1_matches[t1_matches["team2_id"] == tid]

        wins = (m1["team1_score"] > m1["team2_score"]).sum() + (m2["team2_score"] > m2["team1_score"]).sum()
        losses = (m1["team1_score"] < m1["team2_score"]).sum() + (m2["team2_score"] < m2["team1_score"]).sum()
        total_m = wins + losses

        if total_m < min_matches:
            continue

        win_rate = (wins / total_m * 100.0)
        p_sub = pstats[pstats["team_id"] == tid]
        avg_rating = p_sub["effective_rating"].mean()

        team_records.append({
            "rank": row["rank"],
            "team_id": tid,
            "team_name": tname,
            "matches_played": total_m,
            "wins": wins,
            "losses": losses,
            "win_rate_pct": round(win_rate, 2),
            "avg_rating": round(avg_rating, 3) if pd.notnull(avg_rating) else None
        })

    conn.close()
    return pd.DataFrame(team_records), window_label


def plot_tier1_winrate_vs_rating(
    db_path: str = "data/processed/hltv_database.db",
    mode: str = "normalized",
    min_matches: int = 10,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    months: Optional[int] = None,
    output_path: Optional[str] = None,
    show: bool = False
) -> Tuple[plt.Figure, Tuple[plt.Axes, plt.Axes]]:
    """Generates a standalone visualization of Tier 1 Match Win Rate % vs Average Player Rating."""
    df, window_label = load_tier1_team_performance(
        db_path=db_path,
        mode=mode,
        min_matches=min_matches,
        start_date=start_date,
        end_date=end_date,
        months=months
    )
    df = df.sort_values("rank").reset_index(drop=True)

    plt.style.use("dark_background")
    fig = plt.figure(figsize=(16, 9), dpi=180)
    # wspace=0.22 ensures visual separation between left table right edge and scatter plot y-axis label
    gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.0], wspace=0.22)

    ax_table = fig.add_subplot(gs[0, 0])
    ax_plot = fig.add_subplot(gs[0, 1])

    # Left Panel Table
    ax_table.axis("off")
    table_data = []
    for idx, row in df.iterrows():
        table_data.append([
            f"#{row['rank']}",
            row["team_name"],
            f"{row['win_rate_pct']:.1f}%",
            f"{row['avg_rating']:.2f}"
        ])

    col_labels = ["Rank", "Team Name", "Win %", "Rating"]
    table = ax_table.table(
        cellText=table_data,
        colLabels=col_labels,
        loc="center",
        cellLoc="center"
    )
    table.auto_set_font_size(False)
    table.set_fontsize(8.5)
    table.scale(1.0, 1.25)

    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor("#30363D")
        if r == 0:
            cell.set_facecolor("#161B22")
            cell.get_text().set_fontweight("bold")
            cell.get_text().set_color("#58A6FF")
        else:
            cell.set_facecolor("#0D1117" if r % 2 == 0 else "#161B22")
            cell.get_text().set_color("#F0F6FC" if r <= 5 else "#C9D1D9")

    # Specified Title 2: "Top 30 Teams"
    ax_table.set_title("Top 30 Teams", fontsize=14, fontweight="bold", pad=15, color="#F0F6FC")

    # Right Panel Scatter Plot
    bubble_sizes = np.clip(df["matches_played"] * 3.2, 280, 1400)

    scatter = ax_plot.scatter(
        df["avg_rating"],
        df["win_rate_pct"],
        s=bubble_sizes,
        c=df["rank"],
        cmap="viridis_r",
        alpha=0.88,
        edgecolors="white",
        linewidth=0.8,
        zorder=3
    )

    for idx, row in df.iterrows():
        ax_plot.text(
            row["avg_rating"],
            row["win_rate_pct"],
            str(row["rank"]),
            ha="center",
            va="center",
            fontsize=8,
            fontweight="bold",
            color="#FFFFFF",
            zorder=4
        )

    cbar = fig.colorbar(scatter, ax=ax_plot)
    cbar.set_label("Current HLTV Rank", color="#8B949E", fontsize=11)
    cbar.ax.yaxis.set_tick_params(color="#8B949E")
    plt.setp(plt.getp(cbar.ax, "yticklabels"), color="#8B949E")

    if len(df) > 2:
        slope, intercept = np.polyfit(df["avg_rating"], df["win_rate_pct"], 1)
        r_matrix = np.corrcoef(df["avg_rating"], df["win_rate_pct"])
        r_val = r_matrix[0, 1]
        r_squared = r_val ** 2

        x_vals = np.array([df["avg_rating"].min() - 0.01, df["avg_rating"].max() + 0.01])
        y_vals = slope * x_vals + intercept
        
        # Specified Label 4: "Corr: {r}, R^2: {r^2}"
        trend_label = f"Corr: {r_val:+.2f}, $R^2$: {r_squared:.2f}"
        ax_plot.plot(
            x_vals,
            y_vals,
            color="#58A6FF",
            linestyle="--",
            linewidth=1.8,
            alpha=0.8,
            label=trend_label,
            zorder=2
        )
        ax_plot.legend(loc="upper left", facecolor="#161B22", edgecolor="#30363D", fontsize=10)

    # Specified Title 1: "Tier 1 Performance (Team & Player metrics correlation)"
    fig.suptitle("Tier 1 Performance (Team & Player metrics correlation)", fontsize=15, fontweight="bold", color="#F0F6FC", y=0.97)

    # Specified Title 3: "Match Win Rate vs Average Team Rating"
    ax_plot.set_title("Match Win Rate vs Average Team Rating", fontsize=14, fontweight="bold", pad=15, color="#F0F6FC")

    # Specified Label 5: "Match Win Rate, %"
    ax_plot.set_ylabel("Match Win Rate, %", fontsize=12, labelpad=10, color="#C9D1D9")

    # Specified Label 6: "(Normalized if used normalization) Team Rating"
    x_label = "Normalized Team Rating" if mode == "normalized" else "Team Rating"
    ax_plot.set_xlabel(x_label, fontsize=12, labelpad=8, color="#C9D1D9")
    ax_plot.grid(True, linestyle=":", alpha=0.3, color="#30363D")

    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        fig.savefig(output_path, bbox_inches="tight", facecolor="#0D1117")
        print(f"[Plot Saved] {output_path}")

    if show:
        plt.show()

    return fig, (ax_table, ax_plot)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot Tier 1 Win Rate % vs Average Player Rating.")
    parser.add_argument("--mode", choices=["normalized", "raw"], default="raw", help="Rating normalization mode.")
    parser.add_argument("--start-date", type=str, default=None, help="Start date filter (YYYY-MM-DD).")
    parser.add_argument("--end-date", type=str, default=None, help="End date filter (YYYY-MM-DD).")
    parser.add_argument("--months", type=int, default=None, help="Trailing months filter.")
    parser.add_argument("--min-matches", type=int, default=10, help="Minimum Tier 1 matches threshold.")
    parser.add_argument("--out-dir", type=str, default="data/visualization/roster_changes", help="Output directory for plots.")

    args = parser.parse_args()

    out_file = os.path.join(args.out_dir, f"tier1_winrate_vs_rating_{args.mode}.png")
    plot_tier1_winrate_vs_rating(
        mode=args.mode,
        min_matches=args.min_matches,
        start_date=args.start_date,
        end_date=args.end_date,
        months=args.months,
        output_path=out_file
    )
