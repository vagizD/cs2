import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd
import pytest

from ml.features import (
    CONTEXT_COLUMNS,
    FEATURE_COLUMNS,
    feature_matrix,
    inference_examples,
    read_only,
    training_examples,
)
from src.db.schema import CREATE_TABLES_SQL

BUNDLED_DB = Path("data/processed/hltv_database.db")


@pytest.fixture
def temporal_db(tmp_path):
    path = tmp_path / "features.db"
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.executescript(CREATE_TABLES_SQL)
        conn.executemany("INSERT INTO team (team_id, name) VALUES (?, ?)", [
            (4494, "MOUZ"), (9565, "Vitality"), (7020, "Spirit"),
        ])
        conn.executemany("""
            INSERT INTO ranking_snapshot (snapshot_date, rank, team_id, team_name, points)
            VALUES (?, ?, ?, '', ?)
        """, [
            ("2026-01-01", 10, 4494, 200),
            ("2026-01-04", 2, 9565, 850),
            ("2026-01-10", 1, 4494, 999),
            ("2026-01-11", 1, 9565, 999),
        ])
        conn.executemany("""
            INSERT INTO match (match_id, datetime_utc, team1_id, team2_id,
                               team1_score, team2_score, team1_name, team2_name, format)
            VALUES (?, ?, ?, ?, ?, ?, '', '', 'bo3')
        """, [
            (1, "2026-01-06 13:00:00", 7020, 4494, 0, 2),
            (2, "2026-01-09 13:00:00", 9565, 7020, 1, 2),
            (3, "2026-01-10 13:00:00", 9565, 4494, 2, 1),
            (4, "2026-01-10 13:00:00", 9565, 7020, 2, 0),
            (5, "2026-01-11 13:00:00", 9565, 4494, 2, 0),
            (6, "2026-01-07 13:00:00", 4494, 7020, 1, 1),
            (7, "2026-01-07 13:00:00", 4494, 7020, 1, 0),
            (8, "2026-01-07 13:00:00", 4494, 7020, 0, None),
            (9, "2025-11-01 13:00:00", 4494, 7020, 0, 2),
        ])
    return path


def test_point_in_time_parity_and_canonical_labels(temporal_db):
    training = training_examples(temporal_db, (30, 90)).set_index("example_id")
    assert set(training.index) == {1, 2, 3, 4, 5, 9}
    assert training.loc[1, "team_a_won"] == 1
    assert training.loc[3, "team_a_won"] == 0
    assert training.loc[3, "team_a_id"] == 4494
    expected = [8.0, -650.0, 1.0, 0.0, 0.5, 1.0]
    assert feature_matrix(training.loc[[3]]).iloc[0].tolist() == expected
    assert pd.isna(training.loc[1, "rank_diff"])

    inference = inference_examples(
        temporal_db, [(9565, 4494), (4494, 9565)], "2026-01-10 13:00:00", (30, 90)
    )
    assert tuple(inference.columns) == CONTEXT_COLUMNS + FEATURE_COLUMNS
    assert feature_matrix(inference).values.tolist() == [expected, expected]
    assert feature_matrix(training).dtypes.equals(feature_matrix(inference).dtypes)


def test_bundled_snapshot_and_sql_smoke():
    if not BUNDLED_DB.is_file():
        pytest.skip("Bundled SQLite snapshot is absent.")
    with closing(read_only(BUNDLED_DB)) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
    examples = training_examples(BUNDLED_DB, (30, 90))
    assert len(examples) == 16669
    assert examples["example_id"].is_unique
    assert examples["as_of_utc"].is_monotonic_increasing
    assert examples["team_a_won"].isin([0, 1]).all()
