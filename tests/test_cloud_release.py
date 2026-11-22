import os
import signal
import socket
import subprocess
import sys
from pathlib import Path
from time import monotonic, sleep
from unittest.mock import Mock
from urllib.error import URLError
from urllib.request import urlopen

import mlflow
import pytest

from ml.cloud_release import download_model, publish_model
from ml.model_artifact import load_model
from ml.train import train


def test_release_bundle_round_trip_and_snapshot_validation(trained, tmp_path):
    config, snapshot, _, _ = trained
    source, original = load_model(config.model_path)
    stored = {}
    blob = Mock(generation=123)

    def upload(path, *, content_type, if_generation_match):
        assert content_type == "application/zip"
        assert if_generation_match == 0
        stored["bytes"] = Path(path).read_bytes()

    def download(path, *, if_generation_match):
        assert if_generation_match == 123
        Path(path).write_bytes(stored["bytes"])

    blob.upload_from_filename.side_effect = upload
    blob.download_to_filename.side_effect = download

    publish_model(config.model_path, blob)
    output = tmp_path / "serving"
    different = snapshot.model_copy(update={"sha256": "0" * 64})
    with pytest.raises(ValueError, match="different GCS snapshot"):
        download_model(output, blob, different)
    assert list(output.iterdir()) == []

    assert download_model(output, blob, snapshot) == original
    served, _ = load_model(output)
    assert served.named_steps["classifier"].coef_ == pytest.approx(
        source.named_steps["classifier"].coef_
    )


def test_training_logs_model_and_metrics_to_tracking_server(trained, tmp_path):
    config, _, _, _ = trained
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    endpoint = f"http://127.0.0.1:{port}"
    log = tmp_path / "mlflow-server.log"
    executable = Path(sys.executable).with_name("mlflow")
    with log.open("w") as output, subprocess.Popen([
        str(executable), "server", "--host", "127.0.0.1", "--port", str(port),
        "--workers", "1", "--backend-store-uri", f"sqlite:///{tmp_path / 'tracking.db'}",
        "--serve-artifacts", "--artifacts-destination", str(tmp_path / "remote-artifacts"),
    ], stdout=output, stderr=subprocess.STDOUT, start_new_session=True) as server:
        try:
            deadline = monotonic() + 30
            while server.poll() is None and monotonic() < deadline:
                try:
                    with urlopen(f"{endpoint}/health", timeout=1):
                        break
                except (URLError, TimeoutError):
                    sleep(0.15)
            else:
                pytest.fail(f"Tracking server did not start.\n{log.read_text()}")

            remote = config.model_copy(update={
                "mlflow": config.mlflow.model_copy(update={"tracking_uri": endpoint}),
            })
            result = train(remote)
            client = mlflow.MlflowClient(tracking_uri=endpoint)
            run = client.get_run(result["mlflow_run_id"])
            assert run.info.status == "FINISHED"
            assert run.info.artifact_uri.startswith("mlflow-artifacts:/")
            assert run.data.metrics["test_accuracy"] == result["metrics"]["test"]["accuracy"]
            assert {artifact.path for artifact in client.list_artifacts(run.info.run_id)} >= {
                "config.json", "evaluation.json", "export", "plots",
            }
            local = client.download_artifacts(
                run.info.run_id, "export/pipeline.joblib", str(tmp_path)
            )
            assert Path(local).read_bytes() == (config.model_path / "pipeline.joblib").read_bytes()
        finally:
            if server.poll() is None:
                os.killpg(server.pid, signal.SIGTERM)
                server.wait(timeout=15)
