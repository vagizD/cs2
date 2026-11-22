"""Run cloud training and retrieve its sealed model artifact at API startup."""

import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
from zipfile import ZIP_DEFLATED, ZipFile

from google.auth.transport.requests import Request
from google.cloud import storage
from google.cloud.storage.blob import Blob
from google.oauth2.id_token import fetch_id_token

from ml.config import config_parser, database_path, load_config
from ml.gcs import download_snapshot
from ml.model_artifact import METADATA_FILE, PIPELINE_FILE, ModelMetadata
from ml.snapshot import Snapshot, sha256_file


def bundle_blob(client: storage.Client, uri: str) -> Blob:
    parsed = urlsplit(uri)
    key = parsed.path.removeprefix("/")
    if (parsed.scheme != "gs" or not parsed.netloc or parsed.query or parsed.fragment
            or not key.endswith("/model.zip")):
        raise ValueError("MODEL_BUNDLE_URI must name a versioned model.zip in GCS.")
    return client.bucket(parsed.netloc).blob(key)


def publish_model(directory: Path, blob: Blob) -> None:
    with TemporaryDirectory() as temporary:
        archive = Path(temporary) / "model.zip"
        with ZipFile(archive, "w", compression=ZIP_DEFLATED) as bundle:
            for name in (METADATA_FILE, PIPELINE_FILE):
                bundle.write(directory / name, name)
        blob.upload_from_filename(
            str(archive), content_type="application/zip", if_generation_match=0
        )


def download_model(directory: Path, blob: Blob, snapshot: Snapshot) -> ModelMetadata:
    directory.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=directory) as temporary:
        staged = Path(temporary)
        archive = staged / "model.zip"
        blob.reload()
        blob.download_to_filename(str(archive), if_generation_match=int(blob.generation))
        with ZipFile(archive) as bundle:
            if sorted(bundle.namelist()) != sorted((METADATA_FILE, PIPELINE_FILE)):
                raise ValueError("The model bundle must contain exactly the exported model and metadata.")
            for name in (METADATA_FILE, PIPELINE_FILE):
                (staged / name).write_bytes(bundle.read(name))

        metadata = ModelMetadata.model_validate_json((staged / METADATA_FILE).read_bytes())
        trained = metadata.training_snapshot
        if (trained.sha256, trained.gcs_uri, trained.gcs_generation, trained.snapshot_version) != (
            snapshot.sha256, snapshot.gcs_uri, snapshot.gcs_generation, snapshot.snapshot_version
        ):
            raise ValueError("The model was trained from a different GCS snapshot.")
        if sha256_file(staged / PIPELINE_FILE) != metadata.model_sha256:
            raise ValueError("The model bundle failed its checksum verification.")
        for name in (PIPELINE_FILE, METADATA_FILE):
            (staged / name).replace(directory / name)
    return metadata


def main() -> None:
    parser = config_parser("Run a Cloud Run training job or start its serving revision.")
    parser.add_argument("mode", choices=("train", "serve"))
    args = parser.parse_args()
    config = load_config(args.config)

    client = storage.Client()
    artifact = bundle_blob(client, os.environ["MODEL_BUNDLE_URI"])
    db = database_path(config, "gcs")
    snapshot = download_snapshot(db, config.data.gcs_uri, config.data.snapshot_version, client)
    os.environ["DATABASE_PATH"] = str(db)
    if args.mode == "train":
        from ml.build_dataset import build_dataset
        from ml.train import train

        tracking_uri = config.mlflow.tracking_uri.rstrip("/")
        endpoint = urlsplit(tracking_uri)
        if (endpoint.scheme != "https" or not endpoint.hostname or endpoint.path
                or endpoint.username or endpoint.query or endpoint.fragment):
            raise ValueError("Cloud training requires the authenticated MLflow HTTPS service URL.")
        build_dataset(config, db, snapshot)
        os.environ["MLFLOW_TRACKING_TOKEN"] = fetch_id_token(Request(), tracking_uri)
        result = train(config)
        publish_model(config.model_path, artifact)
        print(json.dumps({**result, "model_bundle_uri": os.environ["MODEL_BUNDLE_URI"]}, indent=2))
        return

    download_model(config.model_path, artifact, snapshot)
    os.execv(sys.executable, [
        sys.executable, "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0",
        "--port", os.environ.get("PORT", "8080"),
    ])


if __name__ == "__main__":
    main()
