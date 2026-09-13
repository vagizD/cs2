import sqlite3
import pandas as pd
from pathlib import Path
from typing import Optional

DEFAULT_DB_PATH = Path("data/processed/hltv_database.db")

def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Returns a connection to the SQLite database."""
    conn = sqlite3.connect(db_path)
    return conn

def load_table(table_name: str, db_path: Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    """Loads an entire database table directly into a pandas DataFrame."""
    with get_connection(db_path) as conn:
        return pd.read_sql_query(f"SELECT * FROM {table_name}", conn)

def query(sql_query: str, params: Optional[tuple] = None, db_path: Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    """Executes a custom SQL query and returns the results as a pandas DataFrame."""
    with get_connection(db_path) as conn:
        return pd.read_sql_query(sql_query, conn, params=params)

def get_rankings_df(db_path: Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    """Returns ranking_snapshot table as DataFrame."""
    return load_table("ranking_snapshot", db_path)

def get_matches_df(db_path: Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    """Returns match table as DataFrame."""
    return load_table("match", db_path)

def get_map_results_df(db_path: Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    """Returns map_result table as DataFrame."""
    return load_table("map_result", db_path)

def get_player_stats_df(db_path: Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    """Returns player_map_stats table as DataFrame."""
    return load_table("player_map_stats", db_path)

def get_teams_df(db_path: Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    """Returns team catalog as DataFrame."""
    return load_table("team", db_path)

def get_players_df(db_path: Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    """Returns player catalog as DataFrame."""
    return load_table("player", db_path)

def get_cohort_teams(max_rank: int = 30, db_path: Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    """Returns all unique teams that reached top max_rank at any point."""
    sql = """
        SELECT DISTINCT team_id, team_name, MIN(rank) as peak_rank, COUNT(DISTINCT snapshot_date) as weeks_in_top30
        FROM ranking_snapshot
        WHERE rank <= ?
        GROUP BY team_id, team_name
        ORDER BY peak_rank ASC, weeks_in_top30 DESC
    """
    return query(sql, params=(max_rank,), db_path=db_path)
