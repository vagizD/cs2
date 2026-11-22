#!/usr/bin/env bash
# Runs in Cloud Build after it has checked out and built the requested branch.
set -euo pipefail

: "${GCP_PROJECT:?}"
: "${GCP_REGION:?}"
: "${GCP_ARTIFACT_REPOSITORY:?}"
: "${RELEASE:?}"
: "${SNAPSHOT_VERSION:?}"
: "${GCS_URI:?}"
: "${MODEL_BUNDLE_URI:?}"
: "${MLFLOW_TRACKING_URI:?}"

service=cs2-predictor
training_job="cs2-train-$RELEASE"
release_id="${RELEASE//-/}"
preview_tag="check-${release_id:0:24}"
image_root="$GCP_REGION-docker.pkg.dev/$GCP_PROJECT/$GCP_ARTIFACT_REPOSITORY"
commit="$(cat /workspace/commit)"
region_flags=(--project "$GCP_PROJECT" --region "$GCP_REGION" --quiet)
release_inputs="SNAPSHOT_VERSION=$SNAPSHOT_VERSION,GCS_URI=$GCS_URI,MODEL_BUNDLE_URI=$MODEL_BUNDLE_URI"
# The Cloud SDK image bundles Python outside PATH.
python_bin="$(gcloud info --format='value(basic.python_location)')"
if [[ ! -x "$python_bin" ]]; then
    printf 'Could not locate the Cloud SDK Python interpreter.\n' >&2
    exit 1
fi

image_digest() {
    local name="$1" digest
    digest="$(gcloud artifacts docker images describe "$image_root/$name:$RELEASE" \
        --project "$GCP_PROJECT" --format='value(image_summary.digest)' --quiet)"
    if [[ ! "$digest" =~ ^sha256:[a-f0-9]{64}$ ]]; then
        printf 'Missing registry digest for %s.\n' "$name" >&2
        return 1
    fi
    printf '%s@%s\n' "$image_root/$name" "$digest"
}

# This workflow rolls out revisions of the existing public API.
service_url="$(gcloud run services describe "$service" "${region_flags[@]}" \
    --format='value(status.url)')"
if [[ "$service_url" != https://* ]]; then
    printf 'Set up the predictor service before submitting cloud releases.\n' >&2
    exit 1
fi

training_image="$(image_digest cloud-training)"
serving_image="$(image_digest cloud-serving)"
gcloud run jobs deploy "$training_job" "${region_flags[@]}" \
    --image "$training_image" \
    --service-account "cs2-cloud-trainer@$GCP_PROJECT.iam.gserviceaccount.com" \
    --tasks 1 --parallelism 1 --max-retries 0 --task-timeout 900s --cpu 1 --memory 1Gi \
    --set-env-vars "$release_inputs,MLFLOW_TRACKING_URI=$MLFLOW_TRACKING_URI"
gcloud run jobs execute "$training_job" "${region_flags[@]}" --wait
printf 'Training job %s completed. Model bundle %s\n' "$training_job" "$MODEL_BUNDLE_URI"

gcloud run deploy "$service" "${region_flags[@]}" \
    --image "$serving_image" \
    --service-account "cs2-predictor-runtime@$GCP_PROJECT.iam.gserviceaccount.com" \
    --no-traffic --tag "$preview_tag" --port 8080 \
    --set-env-vars "$release_inputs" \
    --cpu 1 --memory 512Mi --concurrency 8 --timeout 30s --min 0 --max 2 \
    --startup-probe 'httpGet.path=/health,httpGet.port=8080,periodSeconds=5,timeoutSeconds=4,failureThreshold=20'

candidate="$(gcloud run services describe "$service" "${region_flags[@]}" --format=json |
    "$python_bin" -c '
import json, sys
traffic = json.load(sys.stdin)["status"]["traffic"]
entry = next(item for item in traffic if item.get("tag") == sys.argv[1])
print(entry["revisionName"], entry["url"])
' "$preview_tag")"
read -r revision candidate_url <<<"$candidate"
smoke_args=(--wait-seconds 90 --snapshot-version "$SNAPSHOT_VERSION" --git-commit "$commit")
candidate_check="$("$python_bin" -m scripts.smoke_api "$candidate_url" "${smoke_args[@]}")"
printf '%s\n' "$candidate_check"
run_id="$("$python_bin" -c 'import json, sys; print(json.load(sys.stdin)["health"]["mlflow_run_id"])' <<<"$candidate_check")"
if [[ ! "$run_id" =~ ^[a-f0-9]{32}$ ]]; then
    printf 'Candidate version has no recorded MLflow run.\n' >&2
    exit 1
fi
gcloud run services update-traffic "$service" "${region_flags[@]}" \
    --to-revisions "$revision=100" --remove-tags "$preview_tag"
"$python_bin" -m scripts.smoke_api "$service_url" "${smoke_args[@]}" --mlflow-run-id "$run_id"
printf 'Verified release %s from %s at %s\n' "$revision" "$commit" "$service_url"
