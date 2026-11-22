import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from ml.config import load_config
from ml.features import read_only
from ml.model_artifact import METADATA_FILE
from ml.snapshot import inspect_snapshot, manifest_path

MATCHUP = {"team_a_id": 4494, "team_b_id": 9565}


def test_health_teams_probabilities_and_read_only_access(trained):
    config, snapshot, _, _ = trained
    app = create_app(config)
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["data_snapshot_sha256"] == snapshot.sha256
        assert health.json()["ready"] is True
        assert health.json()["as_of_utc"] == "2026-09-08T13:45:01Z"

        teams = client.get("/teams")
        assert teams.status_code == 200
        assert {4494, 9565} <= {team["team_id"] for team in teams.json()}
        assert len(teams.json()) <= config.api.team_limit

        response = client.post("/predict", json=MATCHUP)
        assert response.status_code == 200
        first = response.json()
        assert first == client.post("/predict", json=MATCHUP).json()
        assert first["model_version"] == health.json()["model_version"]
        reverse = client.post("/predict", json={"team_a_id": 9565, "team_b_id": 4494}).json()
        assert first["team_a_win_probability"] == reverse["team_b_win_probability"]
        assert first["team_b_win_probability"] == reverse["team_a_win_probability"]
        assert first["team_a_win_probability"] + first["team_b_win_probability"] == pytest.approx(1)

    with closing(read_only(Path(config.data.local_db_path))) as conn:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            conn.execute("DELETE FROM main.match")


@pytest.mark.parametrize("payload", [
    {"team_a_id": 4494, "team_b_id": 4494},
    {"team_a_id": 4494, "team_b_id": 999999},
    {"team_a_id": "4494", "team_b_id": 9565},
    {"team_a_id": 4494, "team_b_id": 2**63},
    {**MATCHUP, "match_format": "bo3"},
    {},
])
def test_invalid_requests(trained, payload):
    config, _, _, _ = trained
    with TestClient(create_app(config)) as client:
        response = client.post("/predict", json=payload)
        assert response.status_code == 422
        assert response.json()["detail"]


def test_missing_artifacts_return_unavailable(tmp_path):
    config = load_config().model_copy(update={"artifacts_dir": tmp_path})
    with TestClient(create_app(config)) as client:
        for response in [
            client.get("/health"), client.get("/teams"), client.post("/predict", json=MATCHUP)
        ]:
            assert response.status_code == 503
        assert client.get("/health").json()["ready"] is False


def test_newer_snapshot_is_served_with_original_model(trained, tmp_path, monkeypatch):
    config, _, _, _ = trained
    path = tmp_path / "later.db"
    shutil.copyfile(config.data.local_db_path, path)
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute("""
            INSERT INTO ranking_snapshot (snapshot_date, rank, team_id, team_name, points)
            VALUES ('2026-09-14', 3, 4494, 'MOUZ', 801)
        """)
    newer = inspect_snapshot(path, "later-v2")
    manifest_path(path).write_text(newer.model_dump_json(), encoding="utf-8")
    updated = config.model_copy(update={
        "data": config.data.model_copy(update={"snapshot_version": newer.snapshot_version})
    })
    monkeypatch.setenv("DATABASE_PATH", str(path))
    with TestClient(create_app(updated)) as client:
        health = client.get("/health").json()
        assert health["ready"] is True
        assert health["data_snapshot_version"] == "later-v2"
        assert health["training_snapshot_version"] == config.data.snapshot_version
        assert health["as_of_utc"] == "2026-09-15T00:00:00Z"
        response = client.post("/predict", json=MATCHUP)
        assert response.status_code == 200
        assert response.json()["data_snapshot_version"] == "later-v2"


def test_incompatible_model_schema_fails_readiness(trained, tmp_path, monkeypatch):
    config, _, _, _ = trained
    metadata = (config.model_path / METADATA_FILE).read_text(encoding="utf-8")
    (tmp_path / METADATA_FILE).write_text(
        metadata.replace('"rank_diff"', '"incompatible_feature"'), encoding="utf-8"
    )
    monkeypatch.setenv("MODEL_PATH", str(tmp_path))
    with TestClient(create_app(config)) as client:
        assert client.get("/health").status_code == 503
