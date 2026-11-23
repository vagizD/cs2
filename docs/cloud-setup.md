# Deploy in a fresh Google Cloud project

These steps fill in the prerequisites for the existing deployment scripts. They are for a **new, billing-enabled project approved by its owner**, not for reprovisioning the shared demo project. Run commands in Bash from a clean checkout containing the Project 3 code. The existing-project release command remains in the [README](../README.md#snapshot-and-cloud-releases).

Prerequisites: Google Cloud CLI, Docker with BuildKit/buildx, Git, and Python 3.12. The administrator running bootstrap needs permission to enable APIs, create and manage buckets and Artifact Registry, create service accounts and set their IAM policies, set project IAM bindings, deploy Cloud Run, submit Cloud Build jobs, and administer Cloud SQL and Secret Manager. A project administrator can perform bootstrap for a collaborator rather than granting that collaborator project-wide administration. Routine releases use the narrower identities created by `setup_cloud_mlops.sh`.

Cloud SQL, builds, storage, and Cloud Run can incur charges. This procedure creates infrastructure and publishes the predictor and frontend; MLflow and the storage buckets stay private. Organization policies may require an administrator to approve public Cloud Run services.

## 1. Select the new project and enable services

Replace `YOUR_PROJECT_ID` with that project's ID. The snapshot bucket name must be globally unique; change it if the proposed name is taken. Keep the service names below: the release scripts expect `cs2-predictor` and `cs2-mlflow`.

```bash
export GCP_PROJECT=YOUR_PROJECT_ID
export GOOGLE_CLOUD_PROJECT="$GCP_PROJECT"
export GCP_REGION=us-central1
export GCP_ARTIFACT_REPOSITORY=cs2-predictor
export CS2_SNAPSHOT_BUCKET="$GCP_PROJECT-cs2-snapshots"
export CS2_RELEASE_BUCKET="$GCP_PROJECT-cs2-releases"
export GCP_RUN_SERVICE=cs2-predictor
export GCP_RUN_SERVICE_ACCOUNT="cs2-predictor-runtime@$GCP_PROJECT.iam.gserviceaccount.com"
export SNAPSHOT_VERSION=hltv-2026-09-08
export GCS_URI="gs://$CS2_SNAPSHOT_BUCKET/snapshots/$SNAPSHOT_VERSION/hltv_database.db"

gcloud auth login
gcloud auth application-default login
gcloud auth application-default set-quota-project "$GCP_PROJECT"
gcloud services enable --project "$GCP_PROJECT" \
  storage.googleapis.com run.googleapis.com artifactregistry.googleapis.com \
  cloudbuild.googleapis.com logging.googleapis.com iam.googleapis.com \
  sqladmin.googleapis.com secretmanager.googleapis.com
```

## 2. Create the initial registry, bucket, and API identity

These create commands are for resources that do not already exist. On resuming an interrupted setup, inspect existing resources and continue at the next unfinished step.

```bash
gcloud artifacts repositories create "$GCP_ARTIFACT_REPOSITORY" \
  --project "$GCP_PROJECT" --location "$GCP_REGION" --repository-format=docker

gcloud storage buckets create "gs://$CS2_SNAPSHOT_BUCKET" \
  --project "$GCP_PROJECT" --location "$GCP_REGION" \
  --uniform-bucket-level-access --public-access-prevention

for identity in cs2-predictor-runtime cs2-streamlit-runtime; do
  gcloud iam service-accounts create "$identity" --project "$GCP_PROJECT"
done
```

The signed-in deployer needs `iam.serviceAccounts.actAs` on the predictor and frontend identities. An administrator can grant it on these accounts using the following bindings. The command assumes the active CLI identity is a human user; use `serviceAccount:` instead of `user:` for an approved automation identity. Newly created identities can take time to propagate.

```bash
operator_account="$(gcloud auth list --filter=status:ACTIVE --format='value(account)')"
for identity in cs2-predictor-runtime cs2-streamlit-runtime; do
  gcloud iam service-accounts add-iam-policy-binding "$identity@$GCP_PROJECT.iam.gserviceaccount.com" \
    --project "$GCP_PROJECT" --member "user:$operator_account" \
    --role roles/iam.serviceAccountUser --condition=None
done
```

The bootstrap operator also needs to upload the snapshot, push images, and deploy the service. The initial API image contains the verified snapshot and model, so its runtime identity needs no data-bucket access at this stage. The MLOps setup below grants its later cloud-download permissions.

## 3. Publish the frozen snapshot, train, and deploy the initial API

Use the bundled SQLite file as the cleaned input. Uploading inspects its integrity/schema and writes an immutable object plus its generation/checksum manifest. Reusing a snapshot version with different bytes fails; use a new version for a new dataset.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements/training.txt
export ARTIFACTS_DIR="$PWD/artifacts"
export MLFLOW_TRACKING_URI="sqlite:///$PWD/artifacts/bootstrap-mlflow.db"
mkdir -p "$ARTIFACTS_DIR"

DATABASE_PATH=data/processed/hltv_database.db python -m scripts.upload_snapshot
export DATABASE_PATH="$PWD/artifacts/snapshot/hltv_database.db"
python -m ml.build_dataset --source gcs
python -m ml.train
bash scripts/deploy_api.sh prepare
bash scripts/deploy_api.sh deploy
```

The prepare step checks that the model matches the GCS-verified snapshot and builds a Linux AMD64 image. Deploy pushes the prepared image, deploys by digest, and runs an HTTP smoke check. Preserve the printed API URL.

## 4. Provision private tracking and run a managed release

The initial API, registry, and snapshot bucket now satisfy the setup script's prerequisites. This step creates the build/training/tracking identities, private release/artifact buckets, a **billable Cloud SQL instance**, its password secret, and the authenticated MLflow service. It grants the per-resource runtime permissions used by the existing scripts.

```bash
bash scripts/setup_cloud_mlops.sh
bash scripts/release_cloud.sh cloud-mlops "$SNAPSHOT_VERSION"
```

The release script takes a **remote branch name**. Use `main` once the reviewed Project 3 code is merged there, or another reviewed remote branch when appropriate. Cloud Build records its resolved commit, trains from GCS, smoke-tests a zero-traffic candidate, and promotes it only after the checks pass. The command submits asynchronously: wait for Cloud Build to finish successfully and inspect its logs before treating the release as complete.

To inspect a build, substitute the build ID printed by the release command:

```bash
gcloud builds describe BUILD_ID --project "$GCP_PROJECT" --region "$GCP_REGION"
gcloud builds log BUILD_ID --project "$GCP_PROJECT" --region "$GCP_REGION"
```

## 5. Deploy the frontend with its API address

The frontend uses a separate runtime identity with no data-bucket permissions. This creates its service and explicitly configures `API_BASE_URL`; the README's update command assumes that configuration already exists. Run from the repository root after the MLOps setup has finished.

```bash
export API_BASE_URL="$(gcloud run services describe cs2-predictor \
  --project "$GCP_PROJECT" --region "$GCP_REGION" --format='value(status.url)')"
image="$GCP_REGION-docker.pkg.dev/$GCP_PROJECT/$GCP_ARTIFACT_REPOSITORY/cs2-streamlit:git-$(git rev-parse --short=12 HEAD)"
gcloud builds submit app --config deploy/build-image.yaml \
  --project "$GCP_PROJECT" --region "$GCP_REGION" \
  --service-account "projects/$GCP_PROJECT/serviceAccounts/cs2-cloud-build@$GCP_PROJECT.iam.gserviceaccount.com" \
  --gcs-source-staging-dir "gs://$CS2_RELEASE_BUCKET/build-source" \
  --substitutions "_IMAGE=$image"
digest="$(gcloud artifacts docker images describe "$image" \
  --project "$GCP_PROJECT" --format='value(image_summary.digest)')"
[[ "$API_BASE_URL" == https://* && "$digest" =~ ^sha256:[a-f0-9]{64}$ ]]

gcloud run deploy cs2-streamlit --project "$GCP_PROJECT" --region "$GCP_REGION" \
  --image "${image%:*}@$digest" \
  --service-account "cs2-streamlit-runtime@$GCP_PROJECT.iam.gserviceaccount.com" \
  --set-env-vars "API_BASE_URL=$API_BASE_URL" \
  --ingress all --no-invoker-iam-check --port 8080 \
  --cpu 1 --memory 512Mi --min 0 --max 2 --timeout 3600

gcloud run services describe cs2-streamlit --project "$GCP_PROJECT" \
  --region "$GCP_REGION" --format='value(status.url)'
python -m scripts.smoke_api "$API_BASE_URL" --wait-seconds 90 \
  --snapshot-version "$SNAPSHOT_VERSION" --team-ids 4494 9565
```

Open the printed frontend URL in a signed-out/private browser window and test both prediction views. Put the new frontend and API links in the README. Record the successful build ID, serving model version, snapshot, and MLflow run using the [submission checks](submission-checks.md).

This guide has been checked against the repository scripts and CLI references; a fresh-project provisioning run still needs to be completed by an authorized maintainer before claiming it has been tested end to end.

References: [Artifact Registry creation](https://docs.cloud.google.com/sdk/gcloud/reference/artifacts/repositories/create), [private bucket creation](https://docs.cloud.google.com/sdk/gcloud/reference/storage/buckets/create), [Cloud Run deployment](https://docs.cloud.google.com/sdk/gcloud/reference/run/deploy).
