#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <owner/repo>" >&2
  exit 1
fi

FULL_REPO="$1"

set_secret_if_present() {
  local key="$1"
  local val="${!key:-}"
  if [[ -n "${val}" ]]; then
    gh secret set "${key}" --repo "${FULL_REPO}" --body "${val}"
    echo "Set secret: ${key}"
  else
    echo "Skipped secret (missing env): ${key}"
  fi
}

set_secret_if_present "DATABASE_URL"
set_secret_if_present "DIRECT_URL"
set_secret_if_present "N8N_DEPLOY_CALLBACK_URL"
set_secret_if_present "N8N_DEPLOY_CALLBACK_TOKEN"

# Optional until Vercel account exists
set_secret_if_present "VERCEL_TOKEN"
set_secret_if_present "VERCEL_ORG_ID"
set_secret_if_present "VERCEL_PROJECT_ID"

echo "Secret provisioning completed for ${FULL_REPO}."
