#!/usr/bin/env bash
set -euo pipefail

# Cloud Build supplies these arguments. Resolve the image once for both targets.
project_id="$1"
region="$2"
repository="$3"
image_name="$4"
build_id="$5"
pipeline="$6"
bucket="$7"
image_tag="${region}-docker.pkg.dev/${project_id}/${repository}/${image_name}:${build_id}"

# Step 1, DIGEST: Tag -> digest. Tags can be repointed, digests cannot.
digest="$(gcloud artifacts docker images describe "$image_tag" --project="$project_id" --format='value(image_summary.digest)')"
if [[ ! "$digest" =~ ^sha256:[a-f0-9]{64}$ ]]; then
  echo 'Could not resolve a valid image digest' >&2
  exit 1
fi
image_ref="${image_tag%:*}@${digest}"

# Upload only deployment manifests, never application files or local secrets.
bundle_dir="$(mktemp -d)"
mkdir -p "$bundle_dir/deploy_env"
cp skaffold.yaml "$bundle_dir/skaffold.yaml"
cp deploy_env/env-staging.yaml deploy_env/env-production.yaml "$bundle_dir/deploy_env/"

# Step 2, RELEASE: Hand the pinned image + manifests to Cloud Deploy. Staging deploys from here.
gcloud deploy releases create "release-${build_id}" \
  --project="$project_id" --region="$region" \
  --delivery-pipeline="$pipeline" \
  --source="$bundle_dir" \
  --gcs-source-staging-dir="gs://${bucket}/releases" \
  --images="inventra-image-placeholder=${image_ref}" --quiet