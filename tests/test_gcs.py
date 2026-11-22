import os
import shutil
from unittest.mock import Mock

import pytest
from google.api_core.exceptions import PreconditionFailed

from ml.gcs import download_snapshot, upload_snapshot
from ml.snapshot import inspect_snapshot, manifest_path

VERSION = "test-v1"
URI = f"gs://test-bucket/snapshots/{VERSION}/hltv_database.db"


def storage_mock():
    data = Mock(generation=123)
    metadata = Mock()
    client = Mock()
    client.bucket.return_value.blob.side_effect = [metadata, data]
    return client, data, metadata


def test_upload_has_create_only_preconditions_and_manifest(temporal_db):
    client, data, metadata = storage_mock()
    snapshot = upload_snapshot(temporal_db, URI, VERSION, client)
    client.bucket.assert_called_once_with("test-bucket")
    assert data.upload_from_filename.call_args.kwargs["if_generation_match"] == 0
    assert metadata.upload_from_string.call_args.kwargs["if_generation_match"] == 0
    assert snapshot.gcs_generation == 123
    assert snapshot.row_counts["match"] == 9


def test_upload_retries_after_interruption_and_rejects_different_bytes(temporal_db):
    client, data, metadata = storage_mock()
    data.upload_from_filename.side_effect = PreconditionFailed("already exists")
    data.download_to_filename.side_effect = lambda path, **kwargs: shutil.copy(temporal_db, path)
    snapshot = upload_snapshot(temporal_db, URI, VERSION, client)
    assert snapshot.gcs_generation == 123
    data.download_to_filename.assert_called_once()
    metadata.upload_from_string.assert_called_once()

    client, data, metadata = storage_mock()
    data.upload_from_filename.side_effect = PreconditionFailed("already exists")
    data.download_to_filename.side_effect = lambda path, **kwargs: open(path, "wb").close()
    with pytest.raises(ValueError, match="different checksum"):
        upload_snapshot(temporal_db, URI, VERSION, client)
    metadata.upload_from_string.assert_not_called()


@pytest.mark.parametrize("corrupt", [False, True])
def test_download_pins_generation_and_verifies_hash(temporal_db, tmp_path, corrupt):
    client, data, metadata = storage_mock()
    original = inspect_snapshot(temporal_db, VERSION)
    published = original.model_copy(update={"gcs_uri": URI, "gcs_generation": 123})
    metadata.download_as_bytes.return_value = published.model_dump_json().encode()

    def transfer(path, **kwargs):
        assert kwargs == {"if_generation_match": 123}
        assert data.generation == 123
        shutil.copy(temporal_db, path)
        if corrupt:
            with open(path, "ab") as handle:
                handle.write(b"unexpected bytes")

    data.download_to_filename.side_effect = transfer
    key = f"snapshots/{VERSION}/hltv_database.db"
    destination = tmp_path / "download" / "hltv_database.db"
    if corrupt:
        with pytest.raises(ValueError, match="Snapshot manifest mismatch for sha256"):
            download_snapshot(destination, URI, VERSION, client)
        assert not destination.exists()
        assert not manifest_path(destination).exists()
    else:
        assert download_snapshot(destination, URI, VERSION, client) == published
        assert destination.read_bytes() == temporal_db.read_bytes()
        assert manifest_path(destination).is_file()
    client.bucket.return_value.blob.assert_called_with(key, generation=123)


def test_published_snapshot_integration(tmp_path):
    uri = os.environ.get("CS2_GCS_TEST_URI")
    if not uri:
        pytest.skip("Set CS2_GCS_TEST_URI and configure ADC for live GCS verification.")
    version = uri.rsplit("/", 2)[-2]
    assert download_snapshot(tmp_path / "hltv_database.db", uri, version).gcs_generation
