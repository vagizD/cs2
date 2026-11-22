#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
: "${GCP_PROJECT:?Set GCP_PROJECT to the owner-approved Google Cloud project}"
: "${GCP_REGION:?Set GCP_REGION to the Artifact Registry and Cloud Run region}"
: "${GCP_RUN_SERVICE_ACCOUNT:?Set GCP_RUN_SERVICE_ACCOUNT to the Cloud Run service identity}"
repository="${GCP_ARTIFACT_REPOSITORY:-cs2-predictor}"
service="${GCP_RUN_SERVICE:-cs2-predictor}"
python_bin="${PYTHON_BIN:-python}"
host="$GCP_REGION-docker.pkg.dev"
image="$host/$GCP_PROJECT/$repository/$service"
commit="$(git rev-parse --short=12 HEAD)"
tag="git-$commit-$(date -u +%Y%m%dT%H%M%SZ)"

DATABASE_PATH="${DATABASE_PATH:-artifacts/snapshot/hltv_database.db}" \
    "$python_bin" -m scripts.stage_serving --require-gcs --config "${CONFIG_PATH:-config.yaml}"

metadata="$(mktemp)"
trap 'rm -f "$metadata"' EXIT
gcloud auth configure-docker "$host" --quiet
docker buildx build --platform linux/amd64 --target serving --tag "$image:$tag" \
    --label "org.opencontainers.image.revision=$(git rev-parse HEAD)" \
    --provenance=false --metadata-file "$metadata" --push .
digest="$("$python_bin" -c 'import json, sys; print(json.load(open(sys.argv[1]))["containerimage.digest"])' "$metadata")"

gcloud run deploy "$service" --project "$GCP_PROJECT" --region "$GCP_REGION" \
    --image "$image@$digest" --service-account "$GCP_RUN_SERVICE_ACCOUNT" \
    --ingress all --no-invoker-iam-check --port 8080 \
    --cpu 1 --memory 512Mi --concurrency 8 --timeout 30s --min 0 --max 2 \
    --startup-probe 'httpGet.path=/health,httpGet.port=8080,periodSeconds=3,timeoutSeconds=2,failureThreshold=10' \
    --quiet

url="$(gcloud run services describe "$service" --project "$GCP_PROJECT" --region "$GCP_REGION" \
    --format='value(status.url)')"
if [[ "$url" != https://* ]]; then
    printf 'Cloud Run did not return an HTTPS service URL.\n' >&2
    exit 1
fi
"$python_bin" -m scripts.smoke_api "$url" --wait-seconds 45
printf 'Verified public API URL %s\n' "$url"
