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
TEMPLATE_REPO="${GUEST_TEMPLATE_REPO:-TommyKammy/guest-app-template}"
REPO_NAME="${GUEST_SLUG}-${APP_SLUG}"
FULL_REPO="${OWNER}/${REPO_NAME}"

echo "Creating repository: ${FULL_REPO}"
gh repo create "${FULL_REPO}" \
  --private \
  --template "${TEMPLATE_REPO}" \
  --description "${DESCRIPTION}" \
  --clone=false

echo "Repository created: https://github.com/${FULL_REPO}"
