#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <guest-slug> <app-slug> [description]" >&2
  exit 1
fi

GUEST_SLUG="$1"
APP_SLUG="$2"
DESCRIPTION="${3:-Guest app repository}"

OWNER="${GITHUB_OWNER:-TommyKammy}"
FULL_REPO="${OWNER}/${GUEST_SLUG}-${APP_SLUG}"

SCRIPT_DIR="$(dirname "$0")"

"${SCRIPT_DIR}/create_guest_repo.sh" "${GUEST_SLUG}" "${APP_SLUG}" "${DESCRIPTION}"
"${SCRIPT_DIR}/configure_branch_protection.sh" "${FULL_REPO}"
"${SCRIPT_DIR}/set_repo_secrets.sh" "${FULL_REPO}"

if [[ -n "${N8N_PR_WEBHOOK_URL:-}" && -n "${GITHUB_WEBHOOK_SECRET:-}" ]]; then
  "${SCRIPT_DIR}/configure_repo_webhook.sh" "${FULL_REPO}"
else
  echo "Skipping webhook setup (N8N_PR_WEBHOOK_URL/GITHUB_WEBHOOK_SECRET not set)."
fi

echo "Guest app registration complete: https://github.com/${FULL_REPO}"
