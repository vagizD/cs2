from pathlib import Path

import mlflow
import pandas as pd
import pytest

from ml.build_dataset import build_dataset
from ml.config import load_config
from ml.features import feature_matrix
from ml.model_artifact import load_model
from ml.snapshot import inspect_snapshot
from ml.train import chronological_split, read_dataset, train

BUNDLED_DB = Path("data/processed/hltv_database.db")


def test_chronological_split_groups_identical_timestamps():
    frame = pd.DataFrame({
        "example_id": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "as_of_utc": ["01", "01", "02", "02", "03", "04", "05", "05", "06", "07"],
    })
    splits = chronological_split(frame.iloc[::-1], load_config().split)
    train_rows, validation, test = splits.values()
    assert train_rows["as_of_utc"].max() < validation["as_of_utc"].min()
    assert validation["as_of_utc"].max() < test["as_of_utc"].min()
    assert pd.concat(splits.values())["example_id"].is_unique
    assert sum(map(len, splits.values())) == len(frame)


@pytest.fixture(scope="session")
def trained(tmp_path_factory):
    if not BUNDLED_DB.is_file():
        pytest.skip("Bundled SQLite snapshot is absent.")
    root = tmp_path_factory.mktemp("trained")
    defaults = load_config()
    config = defaults.model_copy(update={
        "artifacts_dir": root / "artifacts",
        "mlflow": defaults.mlflow.model_copy(update={
            "tracking_uri": f"sqlite:///{root / 'mlflow.db'}",
        }),
    })
    snapshot = inspect_snapshot(BUNDLED_DB, config.data.snapshot_version)
    first = build_dataset(config, BUNDLED_DB, snapshot)
    mlflow.MlflowClient(tracking_uri=config.mlflow.tracking_uri).create_experiment(
        config.mlflow.experiment_name, artifact_location=(root / "mlruns").as_uri()
    )
    report = train(config)
    return config, snapshot, first, report


def test_reproducible_tracking_and_export(trained):
    config, snapshot, first, report = trained
    original, metadata = load_model(config.model_path)
    dataset, _, _ = read_dataset(config)
    features = feature_matrix(dataset.head(100))
    assert features.isna().any().any()
    probabilities = original.predict_proba(features)
    assert probabilities.shape == (100, 2)

    repeated = build_dataset(config, BUNDLED_DB, snapshot)
    another = train(config)
    second, _ = load_model(config.model_path)
    assert repeated["features_sha256"] == first["features_sha256"]
    assert report["metrics"] == another["metrics"]
    assert second.predict_proba(features) == pytest.approx(probabilities, abs=1e-12)

    client = mlflow.MlflowClient(tracking_uri=config.mlflow.tracking_uri)
    run = client.get_run(report["mlflow_run_id"])
    assert run.data.params["snapshot_sha256"] == snapshot.sha256
    assert run.data.params["random_state"] == "42"
    assert run.data.metrics["test_log_loss"] == report["metrics"]["test"]["log_loss"]
    assert {item.path for item in client.list_artifacts(run.info.run_id, "export")} == {
        "export/pipeline.joblib", "export/metadata.json",
    }
    assert any(a.path == "plots/confusion-matrix.png"
               for a in client.list_artifacts(run.info.run_id, "plots"))
    assert metadata.training_snapshot.sha256 == snapshot.sha256
