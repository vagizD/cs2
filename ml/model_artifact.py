"""The metadata contract for an exported prediction pipeline."""

import hashlib
from pathlib import Path

import joblib
import sklearn
from pydantic import BaseModel, ConfigDict, Field, PositiveInt
from sklearn.pipeline import Pipeline

from ml.features import feature_schema
from ml.snapshot import Snapshot

PIPELINE_FILE = "pipeline.joblib"
METADATA_FILE = "metadata.json"


class ModelMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    model_version: str
    model_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    feature_schema: dict
    lookback_days: tuple[PositiveInt, PositiveInt]
    training_snapshot: Snapshot
    training_dataset_sha256: str
    git_commit: str | None
    sklearn_version: str
    mlflow_run_id: str


def artifact_version(digest: str) -> str:
    return f"logreg-{digest[:16]}"


def load_model(path: Path) -> tuple[Pipeline, ModelMetadata]:
    metadata = ModelMetadata.model_validate_json((path / METADATA_FILE).read_bytes())
    if metadata.feature_schema != feature_schema():
        raise ValueError("Exported model feature schema is incompatible.")
    if metadata.sklearn_version != sklearn.__version__:
        raise ValueError("Exported model requires a different scikit-learn version.")

    pipeline_path = path / PIPELINE_FILE
    with pipeline_path.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
        if digest != metadata.model_sha256 or artifact_version(digest) != metadata.model_version:
            raise ValueError("Exported model checksum or version does not match metadata.")
        handle.seek(0)
        pipeline = joblib.load(handle)

    if (not isinstance(pipeline, Pipeline)
            or list(pipeline.feature_names_in_) != metadata.feature_schema["columns"]
            or pipeline.classes_.tolist() != [0, 1]):
        raise ValueError("Exported model feature inputs or label classes are incompatible.")
    return pipeline, metadata
