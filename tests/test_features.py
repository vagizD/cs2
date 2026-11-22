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

BUNDLED_DB = Path("data/processed/hltv_database.db")


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


@pytest.mark.parametrize("timestamp", [
    "2026-01-10 13:00:00+00:00",
    "2026-01-10 13:00:00.001",
    "2026-01-10T13:00:00",
])
def test_inference_rejects_timestamps_with_different_sql_ordering(temporal_db, timestamp):
    with pytest.raises(ValueError, match="YYYY-MM-DD HH:MM:SS"):
        inference_examples(temporal_db, [(4494, 9565)], timestamp, (30, 90))


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
