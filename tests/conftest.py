import sqlite3
from contextlib import closing

import pytest

from src.db.schema import CREATE_TABLES_SQL


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


@pytest.fixture(scope="session")
def trained(tmp_path_factory):
    from pathlib import Path

    import mlflow

    from ml.build_dataset import build_dataset
    from ml.config import load_config
    from ml.snapshot import inspect_snapshot
    from ml.train import train

    bundled_db = Path("data/processed/hltv_database.db")
    if not bundled_db.is_file():
        pytest.skip("Bundled SQLite snapshot is absent.")
    root = tmp_path_factory.mktemp("trained")
    defaults = load_config()
    config = defaults.model_copy(update={
        "artifacts_dir": root / "artifacts",
        "mlflow": defaults.mlflow.model_copy(update={
            "tracking_uri": f"sqlite:///{root / 'mlflow.db'}",
        }),
    })
    snapshot = inspect_snapshot(bundled_db, config.data.snapshot_version)
    first = build_dataset(config, bundled_db, snapshot)
    mlflow.MlflowClient(tracking_uri=config.mlflow.tracking_uri).create_experiment(
        config.mlflow.experiment_name, artifact_location=(root / "mlruns").as_uri()
    )
    report = train(config)
    return config, snapshot, first, report
