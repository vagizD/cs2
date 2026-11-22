# Cloud training and release

After one-time infrastructure setup, submit a release with a remote Git branch and an immutable snapshot version.

```bash
bash scripts/release_cloud.sh cloud-mlops hltv-2026-09-08
```

Cloud Build fetches the named branch and records the resolved commit. It builds the training and serving images in Artifact Registry and starts a Cloud Run Job. The job downloads the GCS generation recorded in the snapshot manifest, checks the checksum, and trains on the point-in-time SQL features. It sends its metrics, parameters, evaluation plots, and fitted pipeline to the private MLflow service. A create-only ZIP in GCS publishes the serving model once the run succeeds.

Cloud Build starts a candidate revision of the existing predictor with zero production traffic. The candidate loads the snapshot and model from GCS and verifies their provenance before becoming ready. Cloud Build tests the candidate's prediction API and checks its source commit, snapshot version, and MLflow run ID before promoting it. Review the returned build ID in Cloud Build. The build logs report the training job name, bundle URI, model's MLflow run ID, and deployment URL. The workflow prints the build ID immediately and continues in the cloud if your laptop disconnects.

## One-time setup

The existing CS2 predictor service, Artifact Registry repository, and private dataset bucket are prerequisites. The example uses a separate private Cloud Run service for MLflow, a Cloud SQL PostgreSQL instance for experiment metadata, and a dedicated GCS bucket for its model and plot artifacts. Cloud SQL continues to accrue charges independently of Cloud Run's scale-to-zero setting. [MLflow on Google Cloud](https://mlflow.org/docs/latest/self-hosting/deploy-to-cloud/gcp/), [Cloud SQL pricing](https://cloud.google.com/sql/pricing)

Set these variables with the owner-approved project and existing bucket.

```bash
export GCP_PROJECT="your-project-id"
export GCP_REGION="us-central1"
export GCP_ARTIFACT_REPOSITORY="cs2-predictor"
export CS2_SNAPSHOT_BUCKET="your-private-snapshot-bucket"
export CS2_RELEASE_BUCKET="$GCP_PROJECT-cs2-releases"
export CS2_MLFLOW_BUCKET="$GCP_PROJECT-cs2-mlflow"
export CS2_MLFLOW_SQL_INSTANCE="cs2-mlflow-db"
export CS2_MLFLOW_DB_SECRET="cs2-mlflow-db-password"

gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
  storage.googleapis.com cloudbuild.googleapis.com logging.googleapis.com sqladmin.googleapis.com \
  secretmanager.googleapis.com iam.googleapis.com \
  --project "$GCP_PROJECT"

for bucket in "$CS2_RELEASE_BUCKET" "$CS2_MLFLOW_BUCKET"; do
  gcloud storage buckets create "gs://$bucket" --project "$GCP_PROJECT" \
    --location "$GCP_REGION" --uniform-bucket-level-access --public-access-prevention
done

for identity in cs2-cloud-build cs2-cloud-trainer cs2-mlflow-runtime; do
  gcloud iam service-accounts create "$identity" --project "$GCP_PROJECT"
done
```

Run the creation commands once for each resource. The following permissions let the build orchestrator deploy Cloud Run workloads, the trainer write new release artifacts, and the prediction runtime read the requested bundle and SQLite snapshot. The build identity can read the staged source prefix. The MLflow identity can access its own artifact bucket and DB connection.

```bash
build="cs2-cloud-build@$GCP_PROJECT.iam.gserviceaccount.com"
trainer="cs2-cloud-trainer@$GCP_PROJECT.iam.gserviceaccount.com"
tracker="cs2-mlflow-runtime@$GCP_PROJECT.iam.gserviceaccount.com"
predictor="cs2-predictor-runtime@$GCP_PROJECT.iam.gserviceaccount.com"

for role in roles/run.developer roles/logging.logWriter; do
  gcloud projects add-iam-policy-binding "$GCP_PROJECT" --member "serviceAccount:$build" \
    --role "$role" --condition=None
done
gcloud projects add-iam-policy-binding "$GCP_PROJECT" --member "serviceAccount:$tracker" \
  --role roles/cloudsql.client --condition=None

gcloud artifacts repositories add-iam-policy-binding "$GCP_ARTIFACT_REPOSITORY" \
  --project "$GCP_PROJECT" --location "$GCP_REGION" --member "serviceAccount:$build" \
  --role roles/artifactregistry.writer --condition=None

for identity in "$trainer" "$predictor"; do
  gcloud iam service-accounts add-iam-policy-binding "$identity" --project "$GCP_PROJECT" \
    --member "serviceAccount:$build" --role roles/iam.serviceAccountUser --condition=None
  gcloud storage buckets add-iam-policy-binding "gs://$CS2_SNAPSHOT_BUCKET" \
    --member "serviceAccount:$identity" --role roles/storage.objectViewer
done
gcloud storage buckets add-iam-policy-binding "gs://$CS2_RELEASE_BUCKET" \
  --member "serviceAccount:$build" --role roles/storage.objectViewer \
  --condition "expression=resource.name.startsWith('projects/_/buckets/$CS2_RELEASE_BUCKET/objects/build-source/'),title=read-build-source"
gcloud storage buckets add-iam-policy-binding "gs://$CS2_RELEASE_BUCKET" \
  --member "serviceAccount:$trainer" --role roles/storage.objectCreator
gcloud storage buckets add-iam-policy-binding "gs://$CS2_RELEASE_BUCKET" \
  --member "serviceAccount:$predictor" --role roles/storage.objectViewer
gcloud storage buckets add-iam-policy-binding "gs://$CS2_MLFLOW_BUCKET" \
  --member "serviceAccount:$tracker" --role roles/storage.objectUser
```

The user submitting builds also needs Cloud Build submission permission, permission to use the build service account, and permission to stage source files in the release bucket. [Cloud Build IAM](https://docs.cloud.google.com/build/docs/securing-builds/configure-user-specified-service-accounts)

Create the Cloud SQL instance and application database. The shared-core configuration is sized for coursework and small team runs.

```bash
gcloud sql instances create "$CS2_MLFLOW_SQL_INSTANCE" --project "$GCP_PROJECT" \
  --region "$GCP_REGION" --database-version POSTGRES_15 --edition ENTERPRISE \
  --tier db-f1-micro --availability-type ZONAL --storage-size 10 --assign-ip

gcloud sql databases create mlflow --project "$GCP_PROJECT" \
  --instance "$CS2_MLFLOW_SQL_INSTANCE"

python3 -c 'import secrets, sys; sys.stdout.write(secrets.token_urlsafe(32))' |
  gcloud secrets create "$CS2_MLFLOW_DB_SECRET" --project "$GCP_PROJECT" \
    --replication-policy=automatic --data-file=-
python3 scripts/create_mlflow_db_user.py "$GCP_PROJECT" \
  "$CS2_MLFLOW_SQL_INSTANCE" "$CS2_MLFLOW_DB_SECRET"

gcloud secrets add-iam-policy-binding "$CS2_MLFLOW_DB_SECRET" --project "$GCP_PROJECT" \
  --member "serviceAccount:$tracker" --role roles/secretmanager.secretAccessor --condition=None

bash scripts/deploy_mlflow.sh
```

The deploy script grants the training job's identity permission to invoke MLflow. The training container obtains a short-lived ID token for the service and uses the MLflow HTTP API. The service connects to PostgreSQL over the Cloud SQL integration and reads its database password from Secret Manager. [Cloud Run authentication](https://docs.cloud.google.com/run/docs/authenticating/service-to-service), [Cloud SQL from Cloud Run](https://docs.cloud.google.com/sql/docs/postgres/connect-run)

## View and log runs

Grant Cloud Run Invoker (`roles/run.invoker`) and Cloud Run Viewer (`roles/run.viewer`) on the `cs2-mlflow` service to authorized viewers. A viewer can use the Cloud CLI to open the private dashboard through a local proxy.

```bash
gcloud run services proxy cs2-mlflow --project "$GCP_PROJECT" \
  --region "$GCP_REGION" --port 5000
```

Open `http://127.0.0.1:5000` and select the `cs2-match-predictor` experiment. The same proxy can receive metrics from local training with `MLFLOW_TRACKING_URI=http://127.0.0.1:5000 python -m ml.train --config config.yaml`. The Cloud Run Job sends logs to the same tracking service directly. Existing local runs remain available through the local SQLite tracking store. [Authenticated Cloud Run proxy](https://docs.cloud.google.com/sdk/gcloud/reference/run/services/proxy)
