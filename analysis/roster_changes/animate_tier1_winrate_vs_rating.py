import sqlite3
import os
import argparse
import shutil
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
from typing import Optional, List, Tuple


def get_ranking_as_of(conn: sqlite3.Connection, target_date: pd.Timestamp) -> pd.DataFrame:
    """Fetches Top 30 ranking snapshot closest to target_date on or before target_date."""
    target_str = target_date.strftime("%Y-%m-%d")
    row = conn.execute(
        "SELECT MAX(snapshot_date) FROM ranking_snapshot WHERE snapshot_date <= ?",
        [target_str]
    ).fetchone()
    
    snap_date = row[0] if row and row[0] else conn.execute("SELECT MIN(snapshot_date) FROM ranking_snapshot").fetchone()[0]

    df = pd.read_sql_query("""
        SELECT rank, team_id, team_name, points
        FROM ranking_snapshot
        WHERE snapshot_date = ? AND rank <= 30
        ORDER BY rank ASC
    """, conn, params=[snap_date])
    return df


def load_window_performance(
    conn: sqlite3.Connection,
    w_start: pd.Timestamp,
    w_end: pd.Timestamp,
    mode: str = "normalized",
    min_matches: int = 3
) -> pd.DataFrame:
    """Computes team performance metrics for a specific time window [w_start, w_end]."""
    top30_teams = get_ranking_as_of(conn, w_end)
    if top30_teams.empty:
        return pd.DataFrame()

    top30_ids = tuple(top30_teams["team_id"].tolist())

    start_str = w_start.strftime("%Y-%m-%d %H:%M:%S")
    end_str = w_end.strftime("%Y-%m-%d %H:%M:%S")

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
          AND m.datetime_utc >= ? AND m.datetime_utc <= ?
    """, conn, params=[start_str, end_str])

    if t1_matches.empty:
        return pd.DataFrame()

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
          AND m.datetime_utc >= ? AND m.datetime_utc <= ?
    """, conn, params=[start_str, end_str])

    if pstats.empty:
        return pd.DataFrame()

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
            mu = group["rating"].mean()
            sigma = group["rating"].std()
            version_stats[ver] = (mu, sigma)

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

        if pd.notnull(avg_rating):
            team_records.append({
                "rank": row["rank"],
                "team_id": tid,
                "team_name": tname,
                "matches_played": total_m,
                "win_rate_pct": round(win_rate, 2),
                "avg_rating": round(avg_rating, 3)
            })

    return pd.DataFrame(team_records)


def render_single_frame(
    df: pd.DataFrame,
    w_end: pd.Timestamp,
    min_date: pd.Timestamp,
    max_date: pd.Timestamp,
    progress_frac: float,
    frame_path: str,
    mode: str = "normalized",
    is_final_frame: bool = False
):
    """Renders a single frame PNG with exact title and label specifications and clean panel separation."""
    plt.style.use("dark_background")
    fig = plt.figure(figsize=(16, 9), dpi=180)
    # wspace=0.22 ensures no visual overlap between table right edge and scatter plot y-axis label
    gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 0.08], width_ratios=[1.0, 1.0], hspace=0.15, wspace=0.22)

    ax_table = fig.add_subplot(gs[0, 0])
    ax_plot = fig.add_subplot(gs[0, 1])
    ax_timeline = fig.add_subplot(gs[1, :])

    # ---------------------------------------------------------
    # TOP LEFT: Top 30 Teams Table
    # ---------------------------------------------------------
    ax_table.axis("off")
    table_data = []
    if not df.empty:
        df_sorted = df.sort_values("rank").reset_index(drop=True)
        for idx, row in df_sorted.iterrows():
            table_data.append([
                f"#{row['rank']}",
                row["team_name"],
                f"{row['win_rate_pct']:.1f}%",
                f"{row['avg_rating']:.2f}"
            ])
    else:
        table_data = [["-", "No Active Matches", "-", "-"]]

    table = ax_table.table(
        cellText=table_data[:25],
        colLabels=["Rank", "Team Name", "Win %", "Rating"],
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

    # ---------------------------------------------------------
    # TOP RIGHT: Scatter Plot
    # ---------------------------------------------------------
    ax_plot.set_xlim(0.75, 1.35)
    ax_plot.set_ylim(-5, 105)

    if not df.empty:
        bubble_sizes = np.clip(df["matches_played"] * 18, 250, 1200)
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

        if len(df) > 2:
            slope, intercept = np.polyfit(df["avg_rating"], df["win_rate_pct"], 1)
            r_matrix = np.corrcoef(df["avg_rating"], df["win_rate_pct"])
            r_val = r_matrix[0, 1]
            r_sq = r_val ** 2
            x_vals = np.array([0.80, 1.30])
            y_vals = slope * x_vals + intercept
            
            # Specified Label 4: "Corr: {r}, R^2: {r^2}"
            trend_label = f"Corr: {r_val:+.2f}, $R^2$: {r_sq:.2f}"
            ax_plot.plot(
                x_vals, y_vals, color="#58A6FF", linestyle="--", linewidth=1.8, alpha=0.8,
                label=trend_label, zorder=2
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

    # ---------------------------------------------------------
    # BOTTOM: Full-Width Timeline Progress Bar
    # ---------------------------------------------------------
    ax_timeline.axis("off")
    ax_timeline.set_xlim(0, 1)
    ax_timeline.set_ylim(-0.3, 0.8)

    bar_x_start = 0.02
    bar_x_end = 0.98
    bar_y = 0.45
    bar_width = bar_x_end - bar_x_start

    ax_timeline.plot([bar_x_start, bar_x_end], [bar_y, bar_y], color="#30363D", linewidth=4.0, zorder=5)
    current_x = bar_x_start + progress_frac * bar_width
    ax_timeline.plot([bar_x_start, current_x], [bar_y, bar_y], color="#58A6FF", linewidth=4.5, zorder=6)
    
    knob_color = "#3FB950" if is_final_frame else "#58A6FF"
    ax_timeline.plot(current_x, bar_y, marker="o", markersize=9, color=knob_color, markeredgecolor="#FFFFFF", zorder=7)

    start_label = min_date.strftime("%b %Y").upper()
    end_label = max_date.strftime("%b %Y").upper()
    curr_label = w_end.strftime("%b %Y").upper()

    ax_timeline.text(bar_x_start, -0.05, f"START: {start_label}", ha="left", va="top", color="#8B949E", fontsize=9.5, fontweight="bold")
    curr_text = f"CURRENT: {curr_label}" if not is_final_frame else f"TIMELINE END: {curr_label}"
    ax_timeline.text(0.50, -0.05, curr_text, ha="center", va="top", color=knob_color, fontsize=10.5, fontweight="bold")
    ax_timeline.text(bar_x_end, -0.05, f"END: {end_label}", ha="right", va="top", color="#8B949E", fontsize=9.5, fontweight="bold")

    os.makedirs(os.path.dirname(os.path.abspath(frame_path)), exist_ok=True)
    fig.savefig(frame_path, bbox_inches="tight", facecolor="#0D1117")
    plt.close(fig)


def generate_animation_gif(
    db_path: str = "data/processed/hltv_database.db",
    mode: str = "normalized",
    window_days: int = 90,
    stride_days: int = 7,
    min_matches: int = 3,
    fps: float = 12.0,
    pause_sec: float = 2.0,
    output_gif: str = "data/visualization/roster_changes/tier1_winrate_vs_rating_animation.gif"
) -> str:
    """Generates an animated GIF with updated titles, labels, and clean panel spacing."""
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT MIN(datetime_utc), MAX(datetime_utc) FROM match").fetchone()
    min_db = pd.to_datetime(row[0])
    max_db = pd.to_datetime(row[1])

    frames_dir = "data/visualization/roster_changes/temp_frames"
    os.makedirs(frames_dir, exist_ok=True)

    start_end_date = min_db + pd.Timedelta(days=window_days)
    total_span_days = (max_db - start_end_date).total_seconds()

    curr_end = start_end_date
    frame_paths = []
    frame_idx = 0

    print(f"[Animation] Rendering frames with updated titles and clean wspace=0.22...")

    while curr_end <= max_db:
        w_start = curr_end - pd.Timedelta(days=window_days)
        df_win = load_window_performance(conn, w_start, curr_end, mode=mode, min_matches=min_matches)

        elapsed = (curr_end - start_end_date).total_seconds()
        progress_frac = min(1.0, max(0.0, elapsed / total_span_days)) if total_span_days > 0 else 1.0

        is_final = (curr_end + pd.Timedelta(days=stride_days)) > max_db
        frame_file = os.path.join(frames_dir, f"frame_{frame_idx:04d}.png")

        render_single_frame(
            df=df_win,
            w_end=curr_end,
            min_date=start_end_date,
            max_date=max_db,
            progress_frac=progress_frac,
            frame_path=frame_file,
            mode=mode,
            is_final_frame=is_final
        )
        frame_paths.append(frame_file)

        frame_idx += 1
        curr_end += pd.Timedelta(days=stride_days)

    conn.close()

    if not frame_paths:
        raise RuntimeError("No animation frames were generated.")

    pause_frames_count = int(pause_sec * fps)
    first_frame = frame_paths[0]
    final_frame = frame_paths[-1]
    all_frames = [first_frame] * pause_frames_count + frame_paths + [final_frame] * pause_frames_count

    print(f"[Animation] Compiling {len(all_frames)} frames into GIF at {fps} FPS...")
    images = [Image.open(f).convert("RGB") for f in all_frames]
    
    frame_duration_ms = int(1000.0 / fps)
    os.makedirs(os.path.dirname(os.path.abspath(output_gif)), exist_ok=True)
    images[0].save(
        output_gif,
        save_all=True,
        append_images=images[1:],
        duration=frame_duration_ms,
        loop=0,
        disposal=2
    )

    shutil.rmtree(frames_dir, ignore_errors=True)
    print(f"[Animation Saved] {output_gif}")
    return output_gif


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate animated GIF with updated titles and clean panel spacing.")
    parser.add_argument("--mode", choices=["normalized", "raw"], default="raw", help="Rating normalization mode.")
    parser.add_argument("--window-days", type=int, default=90, help="Sliding window duration T in days.")
    parser.add_argument("--stride-days", type=int, default=7, help="Sliding stride step S in days.")
    parser.add_argument("--min-matches", type=int, default=7, help="Minimum matches threshold in window.")
    parser.add_argument("--fps", type=float, default=12.0, help="Frames per second in GIF.")
    parser.add_argument("--pause-sec", type=float, default=2.0, help="Pause duration in seconds at start and end.")
    parser.add_argument("--output", type=str, default="data/visualization/roster_changes/tier1_winrate_vs_rating_animation.gif", help="Output GIF path.")

    args = parser.parse_args()

    generate_animation_gif(
        mode=args.mode,
        window_days=args.window_days,
        stride_days=args.stride_days,
        min_matches=args.min_matches,
        fps=args.fps,
        pause_sec=args.pause_sec,
        output_gif=args.output
    )
