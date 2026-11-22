#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
: "${GCP_PROJECT:?Set GCP_PROJECT to the owner-approved Google Cloud project}"
: "${GCP_REGION:?Set GCP_REGION to the Artifact Registry and Cloud Run region}"
repository="${GCP_ARTIFACT_REPOSITORY:-cs2-predictor}"
service="${GCP_RUN_SERVICE:-cs2-predictor}"
python_bin="${PYTHON_BIN:-python}"
host="$GCP_REGION-docker.pkg.dev"
image="$host/$GCP_PROJECT/$repository/$service"
prepared_image="$image:prepared-locally"

prepare_image() {
    printf 'Validating the serving snapshot and model.\n'
    DATABASE_PATH="${DATABASE_PATH:-artifacts/snapshot/hltv_database.db}" \
        "$python_bin" -m scripts.stage_serving --require-gcs --config "${CONFIG_PATH:-config.yaml}"

    printf 'Building and loading the serving image into local Docker.\n'
    docker buildx build --platform linux/amd64 --target serving --tag "$prepared_image" \
        --label "org.opencontainers.image.revision=$(git rev-parse HEAD)" \
        --progress=plain --provenance=false --load .
    printf 'Prepared local image %s\n' "$prepared_image"
}

registry_digest() {
    gcloud artifacts docker images describe "$1" --project "$GCP_PROJECT" \
        --format='value(image_summary.digest)' --quiet
}

deploy_image() {
    : "${GCP_RUN_SERVICE_ACCOUNT:?Set GCP_RUN_SERVICE_ACCOUNT to the Cloud Run service identity}"

    local image_id ref digest url
    if ! image_id="$(docker image inspect "$prepared_image" --format '{{.Id}}')"; then
        printf 'Prepare the serving image first with bash scripts/deploy_api.sh prepare.\n' >&2
        return 1
    fi
    if [[ ! "$image_id" =~ ^sha256:[0-9a-f]{64}$ ]]; then
        printf 'Docker did not return an image ID for %s.\n' "$prepared_image" >&2
        return 1
    fi

    ref="$image:sha-${image_id#sha256:}"
    printf 'Checking whether %s is already in Artifact Registry.\n' "$ref"
    if ! digest="$(registry_digest "$ref" 2>/dev/null)" || [[ -z "$digest" ]]; then
        gcloud auth configure-docker "$host" --quiet
        docker image tag "$image_id" "$ref"
        printf 'Uploading the prepared image to Artifact Registry.\n'
        docker image push "$ref"
        digest="$(registry_digest "$ref")"
    fi
    if [[ ! "$digest" =~ ^sha256:[0-9a-f]{64}$ ]]; then
        printf 'Artifact Registry did not return a valid image digest for %s.\n' "$ref" >&2
        return 1
    fi

    printf 'Deploying image %s to Cloud Run.\n' "$digest"
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
        return 1
    fi
    "$python_bin" -m scripts.smoke_api "$url" --wait-seconds 45
    printf 'Verified public API URL %s\n' "$url"
}

case "${1:-all}" in
    prepare) prepare_image ;;
    deploy) deploy_image ;;
    all)
        prepare_image
        deploy_image
        ;;
    *)
        printf 'Usage: bash %s [prepare|deploy|all]\n' "$0" >&2
        exit 2
        ;;
esac
