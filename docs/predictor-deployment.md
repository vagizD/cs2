# Deploy the CS2 predictor

The repository includes a Docker serving target, a Cloud Run deployment script, and a Streamlit Community Cloud entrypoint. Live GCS, Cloud Run, and Streamlit URLs are pending owner setup and verification. Run commands from the repository root with the predictor environment from the [README](../README.md#cs2-match-predictor) activated.

## 1. Prepare the Google Cloud project

An owner needs to select a project with billing enabled, choose a region, and approve the private snapshot bucket, Artifact Registry repository, public API, and publication rights for the dataset. Set a budget alert if appropriate. Cloud Run scales to zero between requests, but storage, image retention, and traffic can incur charges. [Google Cloud budgets](https://docs.cloud.google.com/billing/docs/how-to/budgets), [HLTV terms](https://www.hltv.org/terms)

Install Google Cloud CLI and Docker with Buildx. Set the values below to the approved project and an available globally unique bucket name.

```bash
export GCP_PROJECT="your-project-id"
export GCP_REGION="us-central1"
export SNAPSHOT_BUCKET="your-unique-private-bucket"
export GCP_ARTIFACT_REPOSITORY="cs2-predictor"
export GCP_RUN_SERVICE_ACCOUNT="cs2-predictor-runtime@${GCP_PROJECT}.iam.gserviceaccount.com"
export GOOGLE_CLOUD_PROJECT="$GCP_PROJECT"

gcloud auth login
gcloud auth application-default login
gcloud auth application-default set-quota-project "$GCP_PROJECT"

gcloud services enable storage.googleapis.com artifactregistry.googleapis.com \
  run.googleapis.com iam.googleapis.com --project "$GCP_PROJECT"
gcloud storage buckets create "gs://$SNAPSHOT_BUCKET" --project "$GCP_PROJECT" \
  --location "$GCP_REGION" --uniform-bucket-level-access --public-access-prevention
gcloud artifacts repositories create "$GCP_ARTIFACT_REPOSITORY" \
  --project "$GCP_PROJECT" --location "$GCP_REGION" \
  --repository-format docker --immutable-tags
gcloud iam service-accounts create cs2-predictor-runtime --project "$GCP_PROJECT"
```

Run bucket, repository, and service-account creation once per chosen resource. The uploading identity needs object creation and read permissions on the bucket. Reviewers downloading the snapshot need `roles/storage.objectViewer` on that bucket. The deploying identity needs Artifact Registry push access on the repository, Cloud Run deployment and public-access configuration permissions, and `roles/iam.serviceAccountUser` on the named runtime identity. The runtime identity needs no GCS permissions because the image includes the verified snapshot. [GCS ADC](https://docs.cloud.google.com/storage/docs/authentication), [Cloud Run deployment roles](https://docs.cloud.google.com/run/docs/deploying)

## 2. Publish, download, and train on a fixed snapshot

```bash
export SNAPSHOT_VERSION="hltv-2026-09-08"
export GCS_URI="gs://$SNAPSHOT_BUCKET/snapshots/$SNAPSHOT_VERSION/hltv_database.db"

# Publish the original bundled file once as the snapshot owner.
python -m scripts.upload_snapshot --config config.yaml

# A reviewer can begin here with the exact URI, version, and bucket read access.
python -m scripts.download_data --config config.yaml
python -m ml.build_dataset --config config.yaml --source gcs
python -m ml.train --config config.yaml

# Optional authenticated integration verification.
CS2_GCS_TEST_URI="$GCS_URI" python -m pytest -q tests/test_gcs.py
```

Both GCS objects are create-only. The manifest identifies the data object's generation and SHA-256. Transfers verify the pinned generation, checksum, integrity, schema, and manifest statistics. The downloader reuses verified files at the destination. Set `DATABASE_PATH` to a new path when switching versions or replacing a corrupt download. The GCS dataset build checks the snapshot again before extracting features. Use a clean checkout at the recorded commit and the recorded config to reproduce a run.

### Run the GCS workflow in Docker

With standard user ADC created by the CLI, mount the file read-only for the training process. For a federated or workload identity, supply its approved credential configuration.

```bash
docker build --target training --build-arg GIT_COMMIT="$(git rev-parse HEAD)" \
  -t cs2-predictor-training .
mkdir -p artifacts/docker-gcs/mlruns

docker run --rm --user "$(id -u):$(id -g)" \
  -v "$PWD/artifacts/docker-gcs:/app/artifacts" \
  -v "$PWD/artifacts/docker-gcs/mlruns:/app/mlruns" \
  --mount "type=bind,source=$HOME/.config/gcloud/application_default_credentials.json,target=/adc.json,readonly" \
  -e GOOGLE_APPLICATION_CREDENTIALS=/adc.json -e GOOGLE_CLOUD_PROJECT \
  -e GCS_URI -e SNAPSHOT_VERSION -e MLFLOW_TRACKING_URI=sqlite:////app/artifacts/mlflow.db \
  cs2-predictor-training sh -ec 'python -m ml.build_dataset --source gcs && python -m ml.train'
```

The host sees this Docker workflow's database at `artifacts/docker-gcs/snapshot/hltv_database.db` and model at `artifacts/docker-gcs/model`. Set `DATABASE_PATH` and `MODEL_PATH` to these paths before deploying a Docker-trained model.

## 3. Deploy and verify Cloud Run

With `SNAPSHOT_VERSION` set to the downloaded version and the environment still active, run:

```bash
bash scripts/deploy_api.sh
```

The script verifies the serving snapshot and artifact, builds a Linux AMD64 image, pushes it to Artifact Registry, and deploys the exact image digest. The service uses one CPU, 512 MiB memory, a concurrency limit of eight, and zero to two instances. It uses the supported public access flag `--no-invoker-iam-check` and calls the API over HTTPS without credentials to verify readiness, team availability, prediction normalization, and reversal. An organization policy can block public access. [Cloud Run public access](https://docs.cloud.google.com/run/docs/authenticating/public), [CLI deployment reference](https://docs.cloud.google.com/sdk/gcloud/reference/run/deploy)

Record the verified API URL and snapshot URI in the README. If the account requires a separate review, share the GCS object URI and manifest with the reviewer using approved bucket read access.

## 4. Deploy and verify Streamlit

1. Sign in to Streamlit Community Cloud with repository access. Choose **Create app**, select `vagizD/cs2`, choose branch `dev` or the merged release branch, and set the entrypoint to `app/streamlit_app.py`. Select Python 3.12. Community Cloud finds the lean dependency file next to the entrypoint. [Community Cloud deployment](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy), [App dependencies](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies)
2. Set `API_BASE_URL` in the app's TOML secrets to the verified Cloud Run HTTPS URL. [Streamlit secrets](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)

   ```toml
   API_BASE_URL = "https://your-verified-cloud-run-host"
   ```

3. Open the public Streamlit link in a signed-out browser. Pick two eligible teams and submit. Verify both probabilities and compare the data and model versions with the API's `/health`. Record the verified frontend URL in the README.

## Update only the serving snapshot

Publish the compatible SQLite file under a new immutable version. Set `SNAPSHOT_VERSION` and `GCS_URI` for that version, download to a fresh path, and keep `MODEL_PATH` pointing to the original export.

```bash
export SNAPSHOT_VERSION="new-snapshot-version"
export GCS_URI="gs://$SNAPSHOT_BUCKET/snapshots/$SNAPSHOT_VERSION/hltv_database.db"
DATABASE_PATH=/path/to/new/frozen.db python -m scripts.upload_snapshot
export DATABASE_PATH="$PWD/artifacts/snapshots/$SNAPSHOT_VERSION/hltv_database.db"
export MODEL_PATH="$PWD/artifacts/model"
python -m scripts.download_data
bash scripts/deploy_api.sh
```

Each revision starts with the data packaged in its image. The deployed service reports the serving data version and model training data version independently in `/health`. New GCS objects take effect after a new deployment.
