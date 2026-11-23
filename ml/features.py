"""Point-in-time SQLite features shared by training and serving."""

import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

import pandas as pd

SQL_DIR = Path(__file__).with_name("sql")
FEATURE_VERSION = "1"
FEATURE_COLUMNS = (
    "rank_diff",
    "points_diff",
    "win_rate_short_diff",
    "match_count_short_diff",
    "win_rate_long_diff",
    "match_count_long_diff",
)
CONTEXT_COLUMNS = ("example_id", "team_a_id", "team_b_id", "as_of_utc")
TARGET_COLUMN = "team_a_won"
CREATE_CONTEXT = """
CREATE TEMP TABLE prediction_context (
    example_id INTEGER PRIMARY KEY,
    team_a_id INTEGER NOT NULL,
    team_b_id INTEGER NOT NULL CHECK (team_b_id > team_a_id),
    as_of_utc TEXT NOT NULL
)
"""


def read_only(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)


def sql(name: str) -> str:
    return (SQL_DIR / f"{name}.sql").read_text(encoding="utf-8")


def feature_schema() -> dict:
    return {
        "version": FEATURE_VERSION,
        "columns": list(FEATURE_COLUMNS),
        "dtype": "float64",
    }


def feature_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.loc[:, list(FEATURE_COLUMNS)].astype("float64")


def setup_source(conn: sqlite3.Connection) -> None:
    conn.executescript(sql("source"))


def extract_features(conn: sqlite3.Connection, lookbacks: tuple[int, int]) -> pd.DataFrame:
    short, long = lookbacks
    if not 0 < short < long:
        raise ValueError("Lookbacks must be positive, increasing day counts.")
    conn.executescript(sql("history"))
    frame = pd.read_sql_query(
        sql("features"), conn, params={"short_days": short, "long_days": long}
    )
    return frame.astype(dict.fromkeys(FEATURE_COLUMNS, "float64"))


def training_examples(path: Path, lookbacks: tuple[int, int]) -> pd.DataFrame:
    with closing(read_only(path)) as conn:
        setup_source(conn)
        conn.execute(CREATE_CONTEXT)
        conn.executescript(sql("training_contexts"))
        conn.executescript(sql("targets"))
        conn.execute("""
            DELETE FROM prediction_context
            WHERE example_id NOT IN (SELECT example_id FROM ml_targets)
        """)
        features = extract_features(conn, lookbacks)
        targets = pd.read_sql_query("SELECT * FROM ml_targets", conn)
    return features.merge(targets, on="example_id", validate="one_to_one")


def inference_examples(
    path: Path,
    team_pairs: list[tuple[int, int]],
    as_of_utc: str,
    lookbacks: tuple[int, int],
) -> pd.DataFrame:
    timestamp = datetime.fromisoformat(as_of_utc)
    if timestamp.strftime("%Y-%m-%d %H:%M:%S") != as_of_utc:
        raise ValueError("Expected a UTC timestamp formatted as YYYY-MM-DD HH:MM:SS.")
    contexts = [
        (-index, min(team_a, team_b), max(team_a, team_b), as_of_utc)
        for index, (team_a, team_b) in enumerate(team_pairs, start=1)
    ]
    with closing(read_only(path)) as conn:
        setup_source(conn)
        conn.execute(CREATE_CONTEXT)
        conn.executemany("INSERT INTO prediction_context VALUES (?, ?, ?, ?)", contexts)
        # SQL sorts negative context IDs ascending; restore the caller's pair order.
        return extract_features(conn, lookbacks).sort_values(
            "example_id", ascending=False, ignore_index=True
        )


def available_teams(
    path: Path,
    as_of_utc: str,
    lookback_days: int,
    minimum_matches: int,
    limit: int,
) -> list[dict]:
    with closing(read_only(path)) as conn:
        conn.row_factory = sqlite3.Row
        setup_source(conn)
        rows = conn.execute("""
            WITH matches AS (
                SELECT team1_id AS team_id FROM finalized_match
                WHERE datetime_utc >= datetime(:as_of, '-' || :days || ' days')
                  AND datetime_utc < :as_of
                UNION ALL
                SELECT team2_id FROM finalized_match
                WHERE datetime_utc >= datetime(:as_of, '-' || :days || ' days')
                  AND datetime_utc < :as_of
            ), eligible AS (
                SELECT team_id FROM matches
                GROUP BY team_id HAVING count(*) >= :minimum
                ORDER BY count(*) DESC, team_id
                LIMIT :limit
            )
            SELECT t.team_id, t.name FROM eligible JOIN main.team AS t USING (team_id)
            ORDER BY t.name COLLATE NOCASE, t.team_id
        """, {"as_of": as_of_utc, "days": lookback_days,
              "minimum": minimum_matches, "limit": limit})
        return [dict(row) for row in rows]
