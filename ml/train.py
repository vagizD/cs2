"""Fit a deterministic sklearn pipeline and record the run in MLflow."""

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

import joblib
import matplotlib
import mlflow
import mlflow.sklearn
import pandas as pd
import sklearn
from mlflow.models import infer_signature
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ml.config import Config, Split, config_parser, load_config
from ml.features import (
    CONTEXT_COLUMNS,
    FEATURE_COLUMNS,
    TARGET_COLUMN,
    feature_matrix,
    feature_schema,
)
from ml.model_artifact import METADATA_FILE, PIPELINE_FILE, ModelMetadata, artifact_version
from ml.snapshot import Snapshot, sha256_file

matplotlib.use("Agg")
from matplotlib import pyplot as plt


def read_dataset(config: Config) -> tuple[pd.DataFrame, Snapshot, str]:
    directory = config.artifacts_dir / "dataset"
    metadata = json.loads((directory / "dataset.json").read_text(encoding="utf-8"))
    if (metadata["feature_schema"] != feature_schema()
            or metadata["lookback_days"] != list(config.data.lookback_days)):
        raise ValueError("Dataset schema or lookbacks changed. Rebuild the dataset.")
    snapshot = Snapshot.model_validate(metadata["snapshot"])
    if snapshot.snapshot_version != config.data.snapshot_version:
        raise ValueError("Dataset snapshot version changed. Rebuild the dataset.")
    if config.data.gcs_uri and snapshot.gcs_uri != config.data.gcs_uri:
        raise ValueError("Dataset does not come from the configured GCS URI. Build with --source gcs.")

    csv = directory / "features.csv"
    with csv.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
        if digest != metadata["features_sha256"]:
            raise ValueError("Dataset checksum mismatch. Rebuild the dataset.")
        handle.seek(0)
        frame = pd.read_csv(handle, float_precision="round_trip")
    if (tuple(frame.columns) != CONTEXT_COLUMNS + FEATURE_COLUMNS + (TARGET_COLUMN,)
            or len(frame) != metadata["rows"]
            or not frame["example_id"].is_unique
            or not frame[TARGET_COLUMN].isin([0, 1]).all()):
        raise ValueError("Dataset row count, columns, or labels are invalid.")
    return frame, snapshot, digest


def chronological_split(frame: pd.DataFrame, split: Split) -> dict[str, pd.DataFrame]:
    ordered = frame.sort_values(["as_of_utc", "example_id"], ignore_index=True)
    if len(ordered) < 3:
        raise ValueError("At least three timestamped matches are required.")
    times = ordered["as_of_utc"]
    train_stop = times.searchsorted(times.iloc[int(len(ordered) * split.train_fraction)])
    test_stop = times.searchsorted(
        times.iloc[int(len(ordered) * (split.train_fraction + split.val_fraction))]
    )
    if not 0 < train_stop < test_stop < len(ordered):
        raise ValueError("Splits need three nonempty, disjoint timestamp ranges.")
    return {
        "train": ordered.iloc[:train_stop],
        "validation": ordered.iloc[train_stop:test_stop],
        "test": ordered.iloc[test_stop:],
    }


def split_summary(rows: pd.DataFrame) -> dict:
    return {
        "first_utc": rows["as_of_utc"].iloc[0],
        "last_utc": rows["as_of_utc"].iloc[-1],
        "rows": len(rows),
        "canonical_a_wins": int(rows[TARGET_COLUMN].sum()),
        "canonical_b_wins": int((1 - rows[TARGET_COLUMN]).sum()),
    }


def git_provenance() -> tuple[str | None, bool | None]:
    if commit := os.environ.get("GIT_COMMIT"):
        return commit, None
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True
        ).strip()
        changes = subprocess.check_output(
            ["git", "status", "--porcelain"], stderr=subprocess.DEVNULL, text=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None, None
    return commit, bool(changes)


def evaluate(pipeline: Pipeline, subsets: dict[str, pd.DataFrame], plot: Path) -> dict:
    metrics = {}
    figure, axes = plt.subplots(1, len(subsets), figsize=(8, 4), layout="constrained")
    try:
        for (name, rows), axis in zip(subsets.items(), axes, strict=True):
            labels = rows[TARGET_COLUMN]
            data = feature_matrix(rows)
            probabilities = pipeline.predict_proba(data)[:, 1]
            predictions = pipeline.predict(data)
            metrics[name] = {
                "accuracy": accuracy_score(labels, predictions),
                "roc_auc": roc_auc_score(labels, probabilities) if labels.nunique() == 2 else None,
                "log_loss": log_loss(labels, probabilities, labels=[0, 1]),
                "brier_score": brier_score_loss(labels, probabilities),
            }
            ConfusionMatrixDisplay.from_predictions(
                labels, predictions, labels=[0, 1], colorbar=False, ax=axis
            )
            axis.set_title(name.capitalize())
        figure.savefig(plot, dpi=130)
    finally:
        plt.close(figure)
    return metrics


def train(config: Config) -> dict:
    examples, snapshot, dataset_digest = read_dataset(config)
    splits = chronological_split(examples, config.split)
    train_rows = splits["train"]
    if train_rows[TARGET_COLUMN].nunique() != 2:
        raise ValueError("Training requires both canonical outcome classes.")
    pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
        ("scaler", StandardScaler()),
        ("classifier", LogisticRegression(
            C=config.model.c, max_iter=config.model.max_iter, random_state=config.project.random_seed
        )),
    ])
    data = feature_matrix(train_rows)
    pipeline.fit(data, train_rows[TARGET_COLUMN])
    commit, dirty = git_provenance()

    mlflow.set_tracking_uri(config.mlflow.tracking_uri)
    mlflow.set_experiment(config.mlflow.experiment_name)
    output = config.model_path
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output) as workspace:
        stage = Path(workspace)
        pipeline_path = stage / PIPELINE_FILE
        joblib.dump(pipeline, pipeline_path)
        model_digest = sha256_file(pipeline_path)
        plot = stage / "confusion-matrix.png"
        summaries = {name: split_summary(rows) for name, rows in splits.items()}
        metrics = evaluate(pipeline, {key: splits[key] for key in ("validation", "test")}, plot)
        report = {"splits": summaries, "metrics": metrics}

        with mlflow.start_run() as run:
            metadata = ModelMetadata(
                model_version=artifact_version(model_digest),
                model_sha256=model_digest,
                feature_schema=feature_schema(),
                lookback_days=config.data.lookback_days,
                training_snapshot=snapshot,
                training_dataset_sha256=dataset_digest,
                git_commit=commit,
                sklearn_version=sklearn.__version__,
                mlflow_run_id=run.info.run_id,
            )
            mlflow.log_params({
                **pipeline.named_steps["classifier"].get_params(),
                "model_kind": config.model.kind,
                "imputer_strategy": pipeline.named_steps["imputer"].strategy,
                "feature_schema_version": metadata.feature_schema["version"],
                "snapshot_version": snapshot.snapshot_version,
                "snapshot_sha256": snapshot.sha256,
                "snapshot_uri": snapshot.gcs_uri or "bundled-or-local",
                "dataset_sha256": dataset_digest,
                "lookback_days": list(metadata.lookback_days),
                "split_strategy": "chronological_whole_timestamps",
                "git_commit": commit or "unavailable",
                "git_dirty": dirty if dirty is not None else "unknown",
            })
            mlflow.log_metrics({
                f"{subset}_{name}": value
                for subset, scores in metrics.items()
                for name, value in scores.items()
                if value is not None
            })
            mlflow.log_dict(config.model_dump(mode="json"), "config.json")
            mlflow.log_dict(report, "evaluation.json")
            mlflow.log_artifact(str(plot), artifact_path="plots")
            metadata_file = stage / METADATA_FILE
            metadata_file.write_text(metadata.model_dump_json(indent=2) + "\n", encoding="utf-8")
            mlflow.log_artifact(str(pipeline_path), artifact_path="export")
            mlflow.log_artifact(str(metadata_file), artifact_path="export")
            sample = data.head(5)
            mlflow.sklearn.log_model(
                pipeline,
                name="pipeline",
                signature=infer_signature(sample, pipeline.predict(sample)),
                pip_requirements=[
                    f"scikit-learn=={sklearn.__version__}", f"pandas=={pd.__version__}",
                    f"joblib=={joblib.__version__}",
                ],
            )

        pipeline_path.replace(output / PIPELINE_FILE)
        metadata_file.replace(output / METADATA_FILE)
    report["model_version"] = metadata.model_version
    report["mlflow_run_id"] = metadata.mlflow_run_id
    return report


def main() -> None:
    args = config_parser("Train and evaluate the CS2 match predictor.").parse_args()
    print(json.dumps(train(load_config(args.config)), indent=2))


if __name__ == "__main__":
    main()
