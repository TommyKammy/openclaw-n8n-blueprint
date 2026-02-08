#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <owner/repo>" >&2
  exit 1
fi

FULL_REPO="$1"
WEBHOOK_URL="${N8N_PR_WEBHOOK_URL:-}"
WEBHOOK_SECRET="${GITHUB_WEBHOOK_SECRET:-}"

if [[ -z "${WEBHOOK_URL}" ]]; then
  echo "N8N_PR_WEBHOOK_URL is required" >&2
  exit 1
fi

if [[ -z "${WEBHOOK_SECRET}" ]]; then
  echo "GITHUB_WEBHOOK_SECRET is required" >&2
  exit 1
fi

echo "Configuring PR webhook for ${FULL_REPO} -> ${WEBHOOK_URL}"
EXISTING_ID="$(gh api "/repos/${FULL_REPO}/hooks" --jq '.[] | select(.name=="web" and (.events | index("pull_request"))) | .id' | head -n 1 || true)"

if [[ -n "${EXISTING_ID}" ]]; then
  gh api --method PATCH \
    -H "Accept: application/vnd.github+json" \
    "/repos/${FULL_REPO}/hooks/${EXISTING_ID}" \
    --input - <<JSON
{
  "active": true,
  "events": ["pull_request"],
  "config": {
    "url": "${WEBHOOK_URL}",
    "content_type": "json",
    "insecure_ssl": "0",
    "secret": "${WEBHOOK_SECRET}"
  }
}
JSON
  echo "Webhook updated (id=${EXISTING_ID})."
  exit 0
fi

gh api --method POST \
  -H "Accept: application/vnd.github+json" \
  "/repos/${FULL_REPO}/hooks" \
  --input - <<JSON
{
  "name": "web",
  "active": true,
  "events": ["pull_request"],
  "config": {
    "url": "${WEBHOOK_URL}",
    "content_type": "json",
    "insecure_ssl": "0",
    "secret": "${WEBHOOK_SECRET}"
  }
}
JSON

echo "Webhook configured."
