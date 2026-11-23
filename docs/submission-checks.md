# Final reproduction and submission checks

Run these checks on the reviewed code before submitting. This is a procedure, not a record that the checks have already passed. Keep actual outputs with their commit and date. Existing reference metrics and model IDs are in the [README](../README.md).

## 1. Check a clean checkout and the full suite

Use a separate fresh checkout of the branch being reviewed. After the final PR is merged, repeat the submission walkthrough on `main`. Keep the README clone instructions valid if the feature branch is later deleted.

```bash
git status --short
git rev-parse HEAD
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements/test.in
test -s data/processed/hltv_database.db
set -o pipefail
mkdir -p artifacts/submission
python -m pytest -q 2>&1 | tee artifacts/submission/pytest.txt
```

The bundled-database test skips when its input is absent; the explicit file check prevents mistaking that skip for verification of the real snapshot. Investigate other unexpected skips or warnings. The suite includes local HTTP/Streamlit and MLflow-server integration tests, so the environment must permit localhost servers and subprocesses. Save `python -m pip freeze` alongside the test output because `requirements/test.in` specifies direct test dependencies; Docker uses the separately pinned runtime/training requirements.

Then follow **both Docker sections in the README**, building images from this checkout rather than reusing an earlier image. Save the dataset checksum, training report, model metadata, and API smoke output. Check the reported split sizes and validation/test metrics against the documented reference. A new MLflow run ID is expected. Investigate any differing feature checksum or metrics before changing the README's reference values.

## 2. Check the public API and frontend

Run the existing HTTP check against the deployed endpoint, saving its JSON output:

```bash
export API_BASE_URL=https://cs2-predictor-fd3amiehsa-uc.a.run.app
python -m scripts.smoke_api "$API_BASE_URL" --wait-seconds 90 \
  --snapshot-version hltv-2026-09-08 --team-ids 4494 9565 \
  | tee artifacts/submission/public-api.json
```

Use your new service URL and snapshot version if deploying into another project. Confirm these behaviors in a signed-out/private browser window:

- The README frontend link opens, including after the API has been idle. A temporary failure offers a working retry button once the app-recovery change is deployed.
- Two different teams return complementary probabilities. Reversing the teams swaps the results.
- Duplicate teams are rejected. Invalid API inputs return validation errors.
- Eight distinct teams produce a complete bracket and a championship table whose probabilities sum to one. Duplicate seeds show a useful warning and clear the previous result.
- The displayed model, snapshot, and cutoff match the API health response.

Review frontend screenshots and API output from the actual final deployment. A changed source branch does not automatically update either Cloud Run service: the API release and frontend image update are separate operations.

## 3. Export readable evidence from the private MLflow run

An authorized maintainer can export the deployed model's recorded run without making MLflow public. First install the training dependencies in a Python 3.12 virtual environment and run the authenticated proxy in one terminal:

```bash
export GCP_PROJECT=YOUR_PROJECT_ID
gcloud run services proxy cs2-mlflow --project "$GCP_PROJECT" \
  --region us-central1 --port 5000
```

In another terminal at the repository root, use the deployed API URL. This checks that the run's snapshot and training commit match the live model, saves parameters/metrics, and downloads its config, evaluation, model export, and confusion matrix. It reads the existing run; it does not retrain or deploy.

```bash
export API_BASE_URL=https://cs2-predictor-fd3amiehsa-uc.a.run.app
python - <<'PY'
import hashlib
import json
import os
import re
from pathlib import Path
from urllib.request import urlopen
from mlflow import MlflowClient

with urlopen(os.environ["API_BASE_URL"].rstrip("/") + "/health", timeout=90) as response:
    health = json.load(response)
assert health["ready"] is True
run_id = health["mlflow_run_id"]
assert re.fullmatch(r"[a-f0-9]{32}", run_id)
client = MlflowClient(tracking_uri="http://127.0.0.1:5000")
run = client.get_run(run_id)
assert run.info.status == "FINISHED"
assert run.data.params["git_commit"] == health["training_git_commit"]
assert run.data.params["snapshot_version"] == health["data_snapshot_version"]
assert run.data.params["snapshot_sha256"] == health["data_snapshot_sha256"]
output = Path("artifacts/submission") / run_id
output.mkdir(parents=True, exist_ok=False)
(output / "run.json").write_text(json.dumps({
    "run_id": run_id, "status": run.info.status,
    "params": run.data.params, "metrics": run.data.metrics, "health": health,
}, indent=2) + "\n")
for artifact in ("config.json", "evaluation.json", "export", "plots"):
    client.download_artifacts(run_id, artifact, str(output))
metadata = json.loads((output / "export/metadata.json").read_text())
assert metadata["model_version"] == health["model_version"]
assert metadata["mlflow_run_id"] == run_id
assert metadata["git_commit"] == health["training_git_commit"]
assert metadata["training_snapshot"]["sha256"] == health["data_snapshot_sha256"]
with (output / "export/pipeline.joblib").open("rb") as model:
    assert hashlib.file_digest(model, "sha256").hexdigest() == metadata["model_sha256"]
print(output)
PY
```

Keep this export with the submission's supporting materials, or publish the reviewed non-secret evidence in the repository. `artifacts/` is ignored by Git, so generating it alone does not make it accessible to the grader. Confirm that the grader can open the selected evidence without the team's Google Cloud permissions. Never include credentials or the tracking database password. The recorded training commit may precede documentation or frontend-only commits; document that relationship rather than overwriting the model's provenance.

## 4. Final handoff

- Merge the reviewed follow-up fixes into `cloud-mlops` before the final PR to `main`, or explicitly retarget them if that final PR has already merged.
- Run any required API release and frontend update, then repeat the public checks against those versions.
- Confirm both members' Project 3 commits/PRs are visible in GitHub history.
- Submit the repository and public frontend links required by the brief. Ensure the README also links to the API, dataset source, training/local usage, cloud instructions, metrics, and limitations.

A successful local suite and the public demo checks cover different parts of the system. Keep both results, plus the actual Docker and cloud-run evidence; a live health response alone does not verify a clean rebuild or the private tracking artifacts.

Reference: [MLflow client API](https://mlflow.org/docs/latest/api_reference/python_api/mlflow.client.html).
