#!/usr/bin/env bash
# Provision cloud training and private experiment tracking for an existing predictor.
set -euo pipefail
export LC_ALL=C

cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [[ "${1:-}" == --help ]]; then
    printf '%s\n' 'Usage: GCP_PROJECT=PROJECT CS2_SNAPSHOT_BUCKET=BUCKET bash scripts/setup_cloud_mlops.sh'
    printf '%s\n' 'Creates the MLflow service and a billable Cloud SQL instance.'
    exit 0
fi
if [[ $# -ne 0 ]]; then
    printf '%s\n' 'Use --help to see the required environment variables.' >&2
    exit 2
fi

export GCP_PROJECT="${GCP_PROJECT:?Set GCP_PROJECT to the Google Cloud project}"
export GCP_REGION="${GCP_REGION:-us-central1}"
export GCP_ARTIFACT_REPOSITORY="${GCP_ARTIFACT_REPOSITORY:-cs2-predictor}"
export CS2_SNAPSHOT_BUCKET="${CS2_SNAPSHOT_BUCKET:?Set CS2_SNAPSHOT_BUCKET to the snapshot bucket}"
export CS2_RELEASE_BUCKET="${CS2_RELEASE_BUCKET:-$GCP_PROJECT-cs2-releases}"
export CS2_MLFLOW_BUCKET="${CS2_MLFLOW_BUCKET:-$GCP_PROJECT-cs2-mlflow}"
export CS2_MLFLOW_SQL_INSTANCE="${CS2_MLFLOW_SQL_INSTANCE:-cs2-mlflow-db}"
export CS2_MLFLOW_DB_SECRET="${CS2_MLFLOW_DB_SECRET:-cs2-mlflow-db-password}"

project_flags=(--project "$GCP_PROJECT" --quiet)
run_flags=("${project_flags[@]}" --region "$GCP_REGION")
builder="cs2-cloud-build@$GCP_PROJECT.iam.gserviceaccount.com"
trainer="cs2-cloud-trainer@$GCP_PROJECT.iam.gserviceaccount.com"
tracker="cs2-mlflow-runtime@$GCP_PROJECT.iam.gserviceaccount.com"
predictor="cs2-predictor-runtime@$GCP_PROJECT.iam.gserviceaccount.com"

fail() {
    printf '%s\n' "$*" >&2
    exit 1
}

resource_exists() {
    local message
    if message="$("$@" 2>&1)"; then
        return 0
    fi
    case "$message" in
        *NOT_FOUND:*|*'HTTPError 404:'*|*'HTTP Error 404:'*|*'not found: 404.'*) return 1 ;;
        *) fail "$message" ;;
    esac
}

retry_iam_binding() {
    local message status delay
    # Newly created service accounts can take a minute or more to become usable.
    for delay in 2 4 8 16 32 32 0; do
        if message="$("$@" 2>&1)"; then
            return 0
        else
            status=$?
        fi
        if (( delay == 0 )) ||
            [[ "$message" != *"INVALID_ARGUMENT: Service account "*".gserviceaccount.com does not exist"* ]]; then
            printf '%s\n' "$message" >&2
            return "$status"
        fi
        printf 'Waiting %ss for the new service account to propagate.\n' "$delay" >&2
        sleep "$delay"
    done
}

prepare_bucket() {
    local bucket="$1" project_number="$2" description
    if ! resource_exists gcloud storage buckets describe "gs://$bucket" "${project_flags[@]}"; then
        gcloud storage buckets create "gs://$bucket" "${project_flags[@]}" \
            --location "$GCP_REGION" --uniform-bucket-level-access --public-access-prevention
    fi
    description="$(gcloud storage buckets describe "gs://$bucket" \
        "${project_flags[@]}" --raw --format=json)"
    python3 -c '
import json, sys

bucket = json.load(sys.stdin)
policy = bucket.get("iamConfiguration", {})
if str(bucket.get("projectNumber")) != sys.argv[1]:
    sys.exit("Bucket owner project does not match: " + sys.argv[2])
if not policy.get("uniformBucketLevelAccess", {}).get("enabled"):
    sys.exit("Enable uniform bucket-level access for " + sys.argv[2])
if policy.get("publicAccessPrevention") != "enforced":
    sys.exit("Enforce public access prevention for " + sys.argv[2])
' "$project_number" "$bucket" <<<"$description"
}

bucket_role() {
    local bucket="$1" identity="$2" role="$3"
    shift 3
    if [[ $# -eq 0 ]]; then set -- --condition=None; fi
    retry_iam_binding gcloud storage buckets add-iam-policy-binding "gs://$bucket" "${project_flags[@]}" \
        --member "serviceAccount:$identity" --role "$role" "$@" >/dev/null
}

project_role() {
    retry_iam_binding gcloud projects add-iam-policy-binding "$GCP_PROJECT" --quiet \
        --member "serviceAccount:$1" --role "$2" --condition=None >/dev/null
}

account_role() {
    retry_iam_binding gcloud iam service-accounts add-iam-policy-binding "$1" "${project_flags[@]}" \
        --member "$2" --role roles/iam.serviceAccountUser --condition=None >/dev/null
}

configure_database() {
    local location state users deadline
    if ! resource_exists gcloud sql instances describe "$CS2_MLFLOW_SQL_INSTANCE" "${project_flags[@]}"; then
        printf 'Creating the billable Cloud SQL instance. This may take several minutes.\n'
        gcloud sql instances create "$CS2_MLFLOW_SQL_INSTANCE" "${run_flags[@]}" \
            --database-version POSTGRES_15 --edition ENTERPRISE --tier db-f1-micro \
            --availability-type ZONAL --storage-size 10 --assign-ip --async
    fi

    deadline=$((SECONDS + 900))
    while true; do
        read -r location state <<<"$(gcloud sql instances describe "$CS2_MLFLOW_SQL_INSTANCE" \
            "${project_flags[@]}" --format='value(region,state)')"
        [[ "$location" == "$GCP_REGION" ]] || fail "Cloud SQL instance is in $location."
        case "$state" in
            RUNNABLE) break ;;
            PENDING_CREATE|MAINTENANCE)
                (( SECONDS < deadline )) || fail 'Cloud SQL is still starting. Rerun setup to continue.'
                sleep 10
                ;;
            *) fail "Cloud SQL instance has state $state." ;;
        esac
    done
    if ! resource_exists gcloud sql databases describe mlflow \
        "${project_flags[@]}" --instance "$CS2_MLFLOW_SQL_INSTANCE"; then
        gcloud sql databases create mlflow "${project_flags[@]}" --instance "$CS2_MLFLOW_SQL_INSTANCE"
    fi

    users="$(gcloud sql users list "${project_flags[@]}" \
        --instance "$CS2_MLFLOW_SQL_INSTANCE" --format='value(name)')"
    if ! resource_exists gcloud secrets describe "$CS2_MLFLOW_DB_SECRET" "${project_flags[@]}"; then
        if grep -Fxq mlflow <<<"$users"; then
            fail 'The MLflow database user exists. Restore its matching password secret before continuing.'
        fi
        python3 -c 'import secrets, sys; sys.stdout.write(secrets.token_urlsafe(32))' |
            gcloud secrets create "$CS2_MLFLOW_DB_SECRET" "${project_flags[@]}" \
                --replication-policy=automatic --data-file=-
    fi
    if ! grep -Fxq mlflow <<<"$users"; then
        python3 scripts/create_mlflow_db_user.py "$GCP_PROJECT" \
            "$CS2_MLFLOW_SQL_INSTANCE" "$CS2_MLFLOW_DB_SECRET"
    fi
    retry_iam_binding gcloud secrets add-iam-policy-binding "$CS2_MLFLOW_DB_SECRET" "${project_flags[@]}" \
        --member "serviceAccount:$tracker" --role roles/secretmanager.secretAccessor \
        --condition=None >/dev/null
}

setup() {
    local project_number snapshot_owner account operator identity role
    printf 'Checking the existing predictor, Artifact Registry, and snapshot bucket.\n'
    account="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' --quiet)"
    case "$account" in
        *@*.gserviceaccount.com) operator="serviceAccount:$account" ;;
        *@*) operator="user:$account" ;;
        *) fail 'Sign in to Google Cloud with gcloud auth login, then rerun setup.' ;;
    esac
    project_number="$(gcloud projects describe "$GCP_PROJECT" --format='value(projectNumber)' --quiet)"
    snapshot_owner="$(gcloud storage buckets describe "gs://$CS2_SNAPSHOT_BUCKET" \
        "${project_flags[@]}" --raw --format='value(projectNumber)')"
    [[ -n "$project_number" && "$snapshot_owner" == "$project_number" ]] ||
        fail 'The snapshot bucket is outside the configured project.'
    gcloud run services describe cs2-predictor "${run_flags[@]}" >/dev/null
    gcloud artifacts repositories describe "$GCP_ARTIFACT_REPOSITORY" "${project_flags[@]}" \
        --location "$GCP_REGION" >/dev/null

    printf 'Enabling the managed services and preparing two private buckets.\n'
    gcloud services enable storage.googleapis.com run.googleapis.com artifactregistry.googleapis.com \
        cloudbuild.googleapis.com logging.googleapis.com sqladmin.googleapis.com \
        secretmanager.googleapis.com iam.googleapis.com "${project_flags[@]}"
    prepare_bucket "$CS2_RELEASE_BUCKET" "$project_number"
    prepare_bucket "$CS2_MLFLOW_BUCKET" "$project_number"

    printf 'Configuring the build, training, and MLflow service identities.\n'
    for identity in cs2-cloud-build cs2-cloud-trainer cs2-mlflow-runtime; do
        if ! resource_exists gcloud iam service-accounts describe \
            "$identity@$GCP_PROJECT.iam.gserviceaccount.com" "${project_flags[@]}"; then
            gcloud iam service-accounts create "$identity" "${project_flags[@]}"
        fi
    done
    project_role "$builder" roles/run.developer
    project_role "$builder" roles/logging.logWriter
    project_role "$tracker" roles/cloudsql.client

    retry_iam_binding gcloud artifacts repositories add-iam-policy-binding "$GCP_ARTIFACT_REPOSITORY" \
        "${project_flags[@]}" --location "$GCP_REGION" \
        --member "serviceAccount:$builder" --role roles/artifactregistry.writer --condition=None >/dev/null
    account_role "$builder" "$operator"
    account_role "$tracker" "$operator"

    for identity in "$trainer" "$predictor"; do
        account_role "$identity" "serviceAccount:$builder"
        bucket_role "$CS2_SNAPSHOT_BUCKET" "$identity" roles/storage.objectViewer
    done
    bucket_role "$CS2_RELEASE_BUCKET" "$builder" roles/storage.objectViewer \
        --condition "expression=resource.name.startsWith('projects/_/buckets/$CS2_RELEASE_BUCKET/objects/build-source/'),title=read-build-source"
    bucket_role "$CS2_RELEASE_BUCKET" "$trainer" roles/storage.objectCreator
    bucket_role "$CS2_RELEASE_BUCKET" "$predictor" roles/storage.objectViewer
    bucket_role "$CS2_MLFLOW_BUCKET" "$tracker" roles/storage.objectUser

    configure_database
    printf 'Building and deploying the private MLflow service.\n'
    bash scripts/deploy_mlflow.sh

    for role in roles/run.invoker roles/run.viewer; do
        retry_iam_binding gcloud run services add-iam-policy-binding cs2-mlflow "${run_flags[@]}" \
            --member "$operator" --role "$role" --condition=None >/dev/null
    done
    printf '\nTo open MLflow, run this command and visit http://127.0.0.1:5000.\n'
    printf 'gcloud run services proxy cs2-mlflow --project %s --region %s --port 5000\n' \
        "$GCP_PROJECT" "$GCP_REGION"
}

command -v gcloud >/dev/null || fail 'Install the Google Cloud CLI before continuing.'
setup
