#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <owner/repo>" >&2
  exit 1
fi

FULL_REPO="$1"

echo "Applying branch protection to ${FULL_REPO}:main"
set +e
OUTPUT=$(gh api --method PUT \
  -H "Accept: application/vnd.github+json" \
  "/repos/${FULL_REPO}/branches/main/protection" \
  --input - <<'JSON' 2>&1
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "checks"
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false,
    "required_approving_review_count": 1,
    "require_last_push_approval": false
  },
  "restrictions": null,
  "required_linear_history": false,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "required_conversation_resolution": true,
  "lock_branch": false,
  "allow_fork_syncing": true
}
JSON
) 
STATUS=$?
set -e

if [[ ${STATUS} -ne 0 ]]; then
  if [[ "${OUTPUT}" == *"Upgrade to GitHub Pro"* ]]; then
    echo "Branch protection skipped: GitHub plan does not allow private repo branch protection."
    exit 0
  fi
  echo "Failed to configure branch protection:" >&2
  echo "${OUTPUT}" >&2
  exit ${STATUS}
fi

echo "Branch protection configured."
