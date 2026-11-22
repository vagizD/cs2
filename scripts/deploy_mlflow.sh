#!/usr/bin/env bash
# Deploy the tracking service after the one-time infrastructure setup.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
: "${GCP_PROJECT:?Set the Google Cloud project}"
region="${GCP_REGION:-us-central1}"
repository="${GCP_ARTIFACT_REPOSITORY:-cs2-predictor}"
release_bucket="${CS2_RELEASE_BUCKET:-$GCP_PROJECT-cs2-releases}"
artifact_bucket="${CS2_MLFLOW_BUCKET:-$GCP_PROJECT-cs2-mlflow}"
database_instance="${CS2_MLFLOW_SQL_INSTANCE:-cs2-mlflow-db}"
database_secret="${CS2_MLFLOW_DB_SECRET:-cs2-mlflow-db-password}"
service_account="cs2-mlflow-runtime@$GCP_PROJECT.iam.gserviceaccount.com"
build_identity="cs2-cloud-build@$GCP_PROJECT.iam.gserviceaccount.com"
service=cs2-mlflow

connection="$(gcloud sql instances describe "$database_instance" \
    --project "$GCP_PROJECT" --format='value(connectionName)' --quiet)"
version="$(gcloud secrets versions list "$database_secret" --project "$GCP_PROJECT" \
    --filter='state=enabled' --sort-by='~name' --limit=1 --format='value(name)' --quiet)"
version="${version##*/}"
if [[ -z "$connection" || ! "$version" =~ ^[1-9][0-9]*$ ]]; then
    printf 'Provision the Cloud SQL instance and its password secret before deployment.\n' >&2
    exit 1
fi

path="$region-docker.pkg.dev/$GCP_PROJECT/$repository/$service"
tag="git-$(git rev-parse --short=12 HEAD)"
ref="$path:$tag"
describe_image() {
    gcloud artifacts docker images describe "$ref" --project "$GCP_PROJECT" \
        --format='value(image_summary.digest)' --quiet
}
if ! digest="$(describe_image 2>/dev/null)" || [[ -z "$digest" ]]; then
    gcloud builds submit deploy/mlflow --config deploy/mlflow/cloudbuild.yaml \
        --project "$GCP_PROJECT" --region "$region" --suppress-logs \
        --service-account "projects/$GCP_PROJECT/serviceAccounts/$build_identity" \
        --gcs-source-staging-dir "gs://$release_bucket/build-source" \
        --substitutions "_IMAGE=$ref"
    digest="$(describe_image)"
fi
if [[ ! "$digest" =~ ^sha256:[a-f0-9]{64}$ ]]; then
    printf 'Artifact Registry did not return an MLflow image digest.\n' >&2
    exit 1
fi

gcloud run deploy "$service" --project "$GCP_PROJECT" --region "$region" --quiet \
    --image "$path@$digest" --service-account "$service_account" \
    --execution-environment gen2 --invoker-iam-check --no-allow-unauthenticated \
    --set-cloudsql-instances "$connection" --port 8080 \
    --set-env-vars "CLOUD_SQL_CONNECTION=$connection,DB_USER=mlflow,DB_NAME=mlflow,MLFLOW_ARTIFACT_DESTINATION=gs://$artifact_bucket/runs" \
    --set-secrets "DB_PASSWORD=$database_secret:$version" \
    --cpu 1 --memory 1Gi --concurrency 8 --min 0 --max 1 --timeout 120s \
    --startup-probe 'tcpSocket.port=8080,periodSeconds=5,timeoutSeconds=4,failureThreshold=36'

gcloud run services add-iam-policy-binding "$service" --project "$GCP_PROJECT" \
    --region "$region" --member "serviceAccount:cs2-cloud-trainer@$GCP_PROJECT.iam.gserviceaccount.com" \
    --role roles/run.invoker --condition=None --quiet >/dev/null

gcloud run services describe "$service" --project "$GCP_PROJECT" \
    --region "$region" --format='value(status.url)' --quiet
