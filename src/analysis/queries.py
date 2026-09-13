import sqlite3
import pandas as pd
from pathlib import Path
from typing import Optional, Union

DEFAULT_DB_PATH = Path("data/processed/hltv_database.db")

def _get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    return sqlite3.connect(db_path)

def get_top_players(min_maps: int = 30, limit: int = 50, db_path: Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    """
    Returns top players sorted by average HLTV rating, including ADR, KAST %, total kills, deaths, and K/D.
    """
    sql = """
        SELECT p.player_id, p.nickname, p.country_name,
               COUNT(s.map_stats_id) as maps_played,
               ROUND(AVG(s.rating), 2) as avg_rating,
               ROUND(AVG(s.adr), 1) as avg_adr,
               ROUND(AVG(s.kast_pct), 1) as avg_kast,
               SUM(s.kills) as total_kills,
               SUM(s.deaths) as total_deaths,
               ROUND(CAST(SUM(s.kills) AS FLOAT) / NULLIF(SUM(s.deaths), 0), 2) as kd_ratio
        FROM player_map_stats s
        JOIN player p ON s.player_id = p.player_id
        WHERE s.rating IS NOT NULL
        GROUP BY p.player_id, p.nickname
        HAVING maps_played >= ?
        ORDER BY avg_rating DESC
        LIMIT ?
    """
    with _get_connection(db_path) as conn:
        return pd.read_sql_query(sql, conn, params=(min_maps, limit))

def get_team_ranking_history(team_identifier: Union[int, str], db_path: Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    """
    Returns weekly HLTV ranking history for a team (by team_id or team_name).
    """
    if isinstance(team_identifier, int):
        where_clause = "team_id = ?"
        param = team_identifier
    else:
        where_clause = "LOWER(team_name) = LOWER(?)"
        param = str(team_identifier).strip()

    sql = f"""
        SELECT snapshot_date, rank, team_id, team_name, points,
               player_id1, player_id2, player_id3, player_id4, player_id5
        FROM ranking_snapshot
        WHERE {where_clause}
        ORDER BY snapshot_date ASC
    """
    with _get_connection(db_path) as conn:
        return pd.read_sql_query(sql, conn, params=(param,))

def get_match_outcomes(format_filter: Optional[str] = None, db_path: Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    """
    Returns full match list with team scores, winner, format, and UTC datetime.
    """
    params = []
    where_sql = ""
    if format_filter:
        where_sql = "WHERE m.format = ?"
        params.append(format_filter)

    sql = f"""
        SELECT m.match_id, m.event_id, m.datetime_utc, m.format,
               m.team1_id, m.team1_name, m.team2_id, m.team2_name,
               COUNT(mr.map_stats_id) as maps_played,
               SUM(CASE WHEN mr.team1_score > mr.team2_score THEN 1 ELSE 0 END) as team1_maps_won,
               SUM(CASE WHEN mr.team2_score > mr.team1_score THEN 1 ELSE 0 END) as team2_maps_won,
               CASE 
                   WHEN SUM(CASE WHEN mr.team1_score > mr.team2_score THEN 1 ELSE 0 END) > SUM(CASE WHEN mr.team2_score > mr.team1_score THEN 1 ELSE 0 END) THEN m.team1_name
                   WHEN SUM(CASE WHEN mr.team2_score > mr.team1_score THEN 1 ELSE 0 END) > SUM(CASE WHEN mr.team1_score > mr.team2_score THEN 1 ELSE 0 END) THEN m.team2_name
                   ELSE 'Draw/Incomplete'
               END as winner_name
        FROM match m
        LEFT JOIN map_result mr ON m.match_id = mr.match_id
        {where_sql}
        GROUP BY m.match_id
        ORDER BY m.datetime_utc DESC
    """
    with _get_connection(db_path) as conn:
        return pd.read_sql_query(sql, conn, params=params if params else None)

def get_map_pool_analytics(db_path: Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    """
    Returns statistics per CS2 map (total maps played, overtime frequency, average round scores).
    """
    sql = """
        SELECT map_name,
               COUNT(*) as times_played,
               SUM(overtime) as overtime_games,
               ROUND(AVG(team1_score + team2_score), 1) as avg_total_rounds,
               ROUND(CAST(SUM(overtime) AS FLOAT) / COUNT(*) * 100, 1) as overtime_pct
        FROM map_result
        WHERE map_name IS NOT NULL AND map_name != 'Unknown'
        GROUP BY map_name
        ORDER BY times_played DESC
    """
    with _get_connection(db_path) as conn:
        return pd.read_sql_query(sql, conn)

def get_player_performance_detail(player_identifier: Union[int, str], db_path: Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    """
    Returns map-by-map stats for a specific player (by player_id or nickname).
    """
    if isinstance(player_identifier, int):
        where_clause = "s.player_id = ?"
        param = player_identifier
    else:
        where_clause = "LOWER(s.player_name) = LOWER(?)"
        param = str(player_identifier).strip()

    sql = f"""
        SELECT s.map_stats_id, s.match_id, s.player_id, s.player_name, s.team_id,
               s.kills, s.deaths, s.assists, s.adr, s.kast_pct, s.rating,
               mr.map_name, m.datetime_utc, m.format
        FROM player_map_stats s
        JOIN map_result mr ON s.map_stats_id = mr.map_stats_id
        JOIN match m ON s.match_id = m.match_id
        WHERE {where_clause}
        ORDER BY m.datetime_utc DESC
    """
    with _get_connection(db_path) as conn:
        return pd.read_sql_query(sql, conn, params=(param,))

def get_detected_lineup_changes(db_path: Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    """
    Scans consecutive weekly Top-30 ranking snapshots to detect when a team replaced 1 or more players.
    """
    sql = """
        WITH ranked_lineups AS (
            SELECT snapshot_date, rank, team_id, team_name,
                   (COALESCE(player_id1, 0) || ',' || COALESCE(player_id2, 0) || ',' || 
                    COALESCE(player_id3, 0) || ',' || COALESCE(player_id4, 0) || ',' || 
                    COALESCE(player_id5, 0)) as lineup_str,
                   LAG(snapshot_date) OVER (PARTITION BY team_id ORDER BY snapshot_date) as prev_date,
                   LAG(COALESCE(player_id1, 0) || ',' || COALESCE(player_id2, 0) || ',' || 
                       COALESCE(player_id3, 0) || ',' || COALESCE(player_id4, 0) || ',' || 
                       COALESCE(player_id5, 0)) OVER (PARTITION BY team_id ORDER BY snapshot_date) as prev_lineup_str
            FROM ranking_snapshot
            WHERE rank <= 30
        )
        SELECT snapshot_date as change_detected_date, prev_date as prior_snapshot_date,
               team_id, team_name, rank as current_rank,
               lineup_str, prev_lineup_str
        FROM ranked_lineups
        WHERE prev_lineup_str IS NOT NULL AND lineup_str != prev_lineup_str
        ORDER BY snapshot_date DESC
    """
    with _get_connection(db_path) as conn:
        return pd.read_sql_query(sql, conn)

def get_events_summary(is_lan: Optional[bool] = None, event_tier: Optional[str] = None, db_path: Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    """
    Returns event metadata with match counts, prize pools, LAN status, and quality tiers.
    """
    conditions = []
    params = []
    if is_lan is not None:
        conditions.append("e.is_lan = ?")
        params.append(1 if is_lan else 0)
    if event_tier is not None:
        conditions.append("e.event_tier = ?")
        params.append(event_tier)

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    sql = f"""
        SELECT e.event_id, e.name, e.start_date, e.location, e.prize_pool, e.prize_pool_usd,
               e.is_lan, e.event_tier, COUNT(m.match_id) as total_matches
        FROM event e
        LEFT JOIN match m ON e.event_id = m.event_id
        {where_clause}
        GROUP BY e.event_id
        ORDER BY e.prize_pool_usd DESC, total_matches DESC
    """
    with _get_connection(db_path) as conn:
        return pd.read_sql_query(sql, conn, params=params if params else None)

def get_filtered_matches(is_lan: Optional[bool] = None, event_tier: Optional[str] = None, format_filter: Optional[str] = None, min_prize_usd: Optional[int] = None, db_path: Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    """
    Returns matches filtered by LAN status, event tier, format (BO1/BO3/BO5), and minimum prize pool.
    """
    conditions = []
    params = []
    if is_lan is not None:
        conditions.append("e.is_lan = ?")
        params.append(1 if is_lan else 0)
    if event_tier is not None:
        conditions.append("e.event_tier = ?")
        params.append(event_tier)
    if format_filter is not None:
        conditions.append("m.format = ?")
        params.append(format_filter)
    if min_prize_usd is not None:
        conditions.append("e.prize_pool_usd >= ?")
        params.append(min_prize_usd)

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    sql = f"""
        SELECT m.match_id, m.datetime_utc, m.format,
               m.team1_id, m.team1_name, m.team1_score,
               m.team2_id, m.team2_name, m.team2_score,
               e.name as event_name, e.is_lan, e.event_tier, e.prize_pool_usd
        FROM match m
        LEFT JOIN event e ON m.event_id = e.event_id
        {where_clause}
        ORDER BY m.datetime_utc DESC
    """
    with _get_connection(db_path) as conn:
        return pd.read_sql_query(sql, conn, params=params if params else None)

