"""Publish and retrieve immutable snapshot versions using Application Default Credentials."""

import os
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from google.api_core.exceptions import PreconditionFailed
from google.cloud import storage

from ml.snapshot import (
    Snapshot,
    inspect_snapshot,
    manifest_path,
    sha256_file,
    validate_snapshot,
)


def snapshot_blobs(client: storage.Client, uri: str | None, version: str):
    if not uri:
        raise ValueError("Set GCS_URI to gs://BUCKET/snapshots/VERSION/hltv_database.db.")
    parsed = urlsplit(uri)
    key = parsed.path.lstrip("/")
    parts = key.split("/")
    if (
        parsed.scheme != "gs" or not parsed.netloc or parsed.query or parsed.fragment
        or len(parts) < 2 or parts[-2:] != [version, "hltv_database.db"]
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise ValueError("GCS_URI must end in /<snapshot_version>/hltv_database.db.")
    bucket = client.bucket(parsed.netloc)
    return bucket.blob(key), bucket.blob(key + ".manifest.json")


def upload_snapshot(path: Path, uri: str | None, version: str, client=None) -> Snapshot:
    snapshot = inspect_snapshot(path, version)
    if not uri:
        raise ValueError("Set GCS_URI before uploading a snapshot.")
    data_blob, manifest_blob = snapshot_blobs(client or storage.Client(), uri, version)
    with tempfile.TemporaryDirectory() as workspace:
        copy = Path(workspace) / path.name
        shutil.copyfile(path, copy)
        if sha256_file(copy) != snapshot.sha256:
            raise ValueError("The source changed while preparing the upload.")
        try:
            data_blob.upload_from_filename(
                str(copy), content_type="application/vnd.sqlite3", if_generation_match=0
            )
        except PreconditionFailed:
            # An interrupted upload can leave the data object without its manifest.
            data_blob.reload()
            data_blob.download_to_filename(str(copy), if_generation_match=int(data_blob.generation))
            if sha256_file(copy) != snapshot.sha256:
                raise ValueError(f"Snapshot {version} already exists with a different checksum.") from None

    published = snapshot.model_copy(update={
        "gcs_uri": uri, "gcs_generation": int(data_blob.generation)
    })
    try:
        manifest_blob.upload_from_string(
            published.model_dump_json(indent=2),
            content_type="application/json",
            if_generation_match=0,
        )
    except PreconditionFailed:
        existing = Snapshot.model_validate_json(manifest_blob.download_as_bytes())
        if existing.model_dump(exclude={"created_at"}) != published.model_dump(exclude={"created_at"}):
            raise ValueError(f"Snapshot {version} already has a different manifest.") from None
        return existing
    return published


def download_snapshot(path: Path, uri: str | None, version: str, client=None) -> Snapshot:
    if not uri:
        raise ValueError("Set GCS_URI before downloading a snapshot.")
    data_blob, manifest_blob = snapshot_blobs(client or storage.Client(), uri, version)
    manifest = Snapshot.model_validate_json(manifest_blob.download_as_bytes())
    if (manifest.snapshot_version != version or manifest.gcs_uri != uri
            or manifest.gcs_generation is None):
        raise ValueError("GCS manifest does not identify the requested snapshot and generation.")

    path.parent.mkdir(parents=True, exist_ok=True)
    sidecar = manifest_path(path)
    with tempfile.TemporaryDirectory(dir=path.parent) as workspace:
        staged = Path(workspace) / path.name
        if path.exists():
            validate_snapshot(path, manifest)
        else:
            data_blob.generation = manifest.gcs_generation
            data_blob.download_to_filename(
                str(staged), if_generation_match=manifest.gcs_generation
            )
            validate_snapshot(staged, manifest)
            try:
                os.link(staged, path)
            except FileExistsError:
                validate_snapshot(path, manifest)

        staged_manifest = manifest_path(staged)
        staged_manifest.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
        try:
            os.link(staged_manifest, sidecar)
        except FileExistsError:
            if Snapshot.model_validate_json(sidecar.read_bytes()) != manifest:
                raise ValueError(f"{sidecar} describes a different snapshot. Choose a new output path.") from None
    return manifest
