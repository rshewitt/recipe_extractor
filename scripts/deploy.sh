#!/usr/bin/env bash
set -euo pipefail

STACK_NAME="${STACK_NAME:-recipe-extractor-prod}"
AWS_REGION="${AWS_REGION:-us-west-2}"
ENVIRONMENT="${ENVIRONMENT:-prod}"
BEDROCK_MODEL_ID="${BEDROCK_MODEL_ID:-us.anthropic.claude-haiku-4-5-20251001-v1:0}"

command -v poetry >/dev/null || { echo "Poetry is required." >&2; exit 1; }
command -v sam >/dev/null || { echo "AWS SAM CLI is required." >&2; exit 1; }
command -v aws >/dev/null || { echo "AWS CLI is required." >&2; exit 1; }

if [[ ! -f poetry.lock ]]; then
  echo "poetry.lock is missing; generating it before the build."
  poetry lock
fi

sam build
sam deploy \
  --stack-name "$STACK_NAME" \
  --region "$AWS_REGION" \
  --resolve-s3 \
  --capabilities CAPABILITY_IAM \
  --no-fail-on-empty-changeset \
  --parameter-overrides \
    Environment="$ENVIRONMENT" \
    BedrockModelId="$BEDROCK_MODEL_ID"

frontend_bucket="$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" --region "$AWS_REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`FrontendBucketName`].OutputValue' --output text)"

distribution_id="$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" --region "$AWS_REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`DistributionId`].OutputValue' --output text)"

site_url="$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" --region "$AWS_REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`SiteUrl`].OutputValue' --output text)"

aws s3 sync frontend/ "s3://${frontend_bucket}/" \
  --delete \
  --cache-control 'public,max-age=300' \
  --region "$AWS_REGION"

aws s3 cp frontend/index.html "s3://${frontend_bucket}/index.html" \
  --content-type 'text/html; charset=utf-8' \
  --cache-control 'no-cache,max-age=0,must-revalidate' \
  --region "$AWS_REGION"

aws cloudfront create-invalidation --distribution-id "$distribution_id" --paths '/*' >/dev/null
printf 'Deployed: %s\n' "$site_url"
