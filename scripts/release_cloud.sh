#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
if [[ "$#" != 2 ]]; then
    printf 'Usage: bash %s GIT_BRANCH SNAPSHOT_VERSION\n' "$0" >&2
    exit 2
fi
branch="$1"
version="$2"
git check-ref-format --branch "$branch" >/dev/null
if [[ "$branch" == @\{* || ! "$version" =~ ^[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}$ ]]; then
    printf 'Provide a remote Git branch name and a valid snapshot version.\n' >&2
    exit 2
fi
: "${GCP_PROJECT:?Set the Google Cloud project from the one-time provisioning steps}"
: "${CS2_SNAPSHOT_BUCKET:?Set the existing GCS snapshot bucket}"
region="${GCP_REGION:-us-central1}"
repository="${GCP_ARTIFACT_REPOSITORY:-cs2-predictor}"
release_bucket="${CS2_RELEASE_BUCKET:-$GCP_PROJECT-cs2-releases}"
build_identity="cs2-cloud-build@$GCP_PROJECT.iam.gserviceaccount.com"
mlflow_url="$(gcloud run services describe cs2-mlflow --project "$GCP_PROJECT" \
    --region "$region" --format='value(status.url)' --quiet)"
if [[ "$mlflow_url" != https://* ]]; then
    printf 'Provision the authenticated cs2-mlflow service before releasing.\n' >&2
    exit 1
fi

delimiter="__CS2__"
while [[ "$branch" == *"$delimiter"* ]]; do delimiter="_$delimiter"; done
substitutions=("_BRANCH=$branch" "_SNAPSHOT_VERSION=$version" "_REGION=$region"
    "_REPOSITORY=$repository" "_SNAPSHOT_BUCKET=$CS2_SNAPSHOT_BUCKET"
    "_RELEASE_BUCKET=$release_bucket" "_MLFLOW_URL=$mlflow_url")
printf -v overrides "%s$delimiter" "${substitutions[@]}"

gcloud builds submit deploy --config deploy/cloudbuild.yaml --project "$GCP_PROJECT" \
    --region "$region" --async \
    --service-account "projects/$GCP_PROJECT/serviceAccounts/$build_identity" \
    --gcs-source-staging-dir "gs://$release_bucket/build-source" \
    --substitutions "^${delimiter}^${overrides%$delimiter}"
