#!/usr/bin/env bash
# One-time: create the S3 bucket that stores Terraform state (shared by your laptop and GitHub Actions).
# Usage: ./scripts/bootstrap_state.sh [owner]   (default owner: robby)
set -euo pipefail
OWNER="${1:-robby}"
REGION="${AWS_REGION:-us-east-1}"
SUFFIX=$(openssl rand -hex 3)   # (tr|head on /dev/urandom dies silently under pipefail on macOS)
BUCKET="phytro-${OWNER}-tfstate-${SUFFIX}"

aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" >/dev/null
aws s3api put-bucket-versioning --bucket "$BUCKET" --versioning-configuration Status=Enabled
aws s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-encryption --bucket "$BUCKET" --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

cat > "$(dirname "$0")/../infra/backend.hcl" <<EOF
bucket       = "${BUCKET}"
key          = "phytro/terraform.tfstate"
region       = "${REGION}"
use_lockfile = true
encrypt      = true
EOF
echo "✅ State bucket: ${BUCKET}"
echo "   Wrote infra/backend.hcl. Add TF_STATE_BUCKET=${BUCKET} as a GitHub Actions secret."
