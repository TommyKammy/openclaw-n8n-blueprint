#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="${ROOT_DIR}/scripts/teams/create_or_renew_graph_subscription.sh"

if [[ ! -x "$SCRIPT" ]]; then
  echo "Missing executable helper: $SCRIPT" >&2
  exit 1
fi

MODE="${MODE:-renew}"

if [[ "$MODE" == "create" ]]; then
  exec "$SCRIPT"
fi

# Default renew flow:
exec MODE=renew "$SCRIPT"
