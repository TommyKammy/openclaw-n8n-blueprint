#!/usr/bin/env bash
set -euo pipefail

# Microsoft Graph subscription helper for Teams/Entra guest provisioning webhook.
#
# Creates or renews a Graph subscription pointing to:
#   https://<domain>/teams/events
#
# Requires app-only token permissions (example):
# - User.Read.All (Application)
# - Directory.Read.All (Application)
#
# Usage:
#   MODE=create ./scripts/teams/create_or_renew_graph_subscription.sh
#   MODE=renew  SUBSCRIPTION_ID=<id> ./scripts/teams/create_or_renew_graph_subscription.sh
#
# Required env:
#   TENANT_ID
#   GRAPH_CLIENT_ID
#   GRAPH_CLIENT_SECRET
#   PUBLIC_BASE_URL           (e.g. https://n8n-s-app01.tmcast.net)
#   TEAMS_CLIENT_STATE        (must match provisioner env)
#
# Optional env:
#   MODE=create|renew         (default: create)
#   SUBSCRIPTION_ID           (required for MODE=renew)
#   GRAPH_RESOURCE            (default: /users)
#   GRAPH_CHANGE_TYPE         (default: updated)
#   EXPIRY_MINUTES            (default: 2880 = 48h)
#   SUBSCRIPTION_STATE_FILE   (default: ./scripts/teams/subscription-id.txt)

MODE="${MODE:-create}"
TENANT_ID="${TENANT_ID:-}"
CLIENT_ID="${GRAPH_CLIENT_ID:-}"
CLIENT_SECRET="${GRAPH_CLIENT_SECRET:-}"
PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-}"
TEAMS_CLIENT_STATE="${TEAMS_CLIENT_STATE:-}"
SUBSCRIPTION_ID="${SUBSCRIPTION_ID:-}"
GRAPH_RESOURCE="${GRAPH_RESOURCE:-/users}"
GRAPH_CHANGE_TYPE="${GRAPH_CHANGE_TYPE:-updated}"
EXPIRY_MINUTES="${EXPIRY_MINUTES:-2880}"
SUBSCRIPTION_STATE_FILE="${SUBSCRIPTION_STATE_FILE:-./scripts/teams/subscription-id.txt}"

if [[ -z "$TENANT_ID" || -z "$CLIENT_ID" || -z "$CLIENT_SECRET" || -z "$PUBLIC_BASE_URL" || -z "$TEAMS_CLIENT_STATE" ]]; then
  echo "Missing required env. Need TENANT_ID, GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET, PUBLIC_BASE_URL, TEAMS_CLIENT_STATE" >&2
  exit 1
fi

if [[ "$MODE" != "create" && "$MODE" != "renew" ]]; then
  echo "MODE must be create or renew" >&2
  exit 1
fi

if [[ "$MODE" == "renew" && -z "$SUBSCRIPTION_ID" ]]; then
  if [[ -f "$SUBSCRIPTION_STATE_FILE" ]]; then
    SUBSCRIPTION_ID="$(tr -d '[:space:]' < "$SUBSCRIPTION_STATE_FILE")"
  fi
fi

if [[ "$MODE" == "renew" && -z "$SUBSCRIPTION_ID" ]]; then
  echo "SUBSCRIPTION_ID is required for renew mode" >&2
  exit 1
fi

NOTIFICATION_URL="${PUBLIC_BASE_URL%/}/teams/events"

EXPIRES_AT="$(python3 - <<PY
import datetime
mins=int(${EXPIRY_MINUTES})
dt=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=mins)
print(dt.replace(microsecond=0).isoformat().replace('+00:00','Z'))
PY
)"

TOKEN_JSON="$(curl -sS -X POST "https://login.microsoftonline.com/${TENANT_ID}/oauth2/v2.0/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "client_id=${CLIENT_ID}" \
  --data-urlencode "client_secret=${CLIENT_SECRET}" \
  --data-urlencode "scope=https://graph.microsoft.com/.default" \
  --data-urlencode "grant_type=client_credentials")"

ACCESS_TOKEN="$(python3 - <<PY
import json
obj=json.loads('''${TOKEN_JSON}''')
print(obj.get('access_token',''))
PY
)"

if [[ -z "$ACCESS_TOKEN" ]]; then
  echo "Failed to obtain Graph access token" >&2
  echo "$TOKEN_JSON" >&2
  exit 1
fi

if [[ "$MODE" == "create" ]]; then
  BODY="$(python3 - <<PY
import json
obj={
  "changeType":"${GRAPH_CHANGE_TYPE}",
  "notificationUrl":"${NOTIFICATION_URL}",
  "resource":"${GRAPH_RESOURCE}",
  "expirationDateTime":"${EXPIRES_AT}",
  "clientState":"${TEAMS_CLIENT_STATE}",
}
print(json.dumps(obj,separators=(',',':')))
PY
)"

  RESP="$(curl -sS -X POST "https://graph.microsoft.com/v1.0/subscriptions" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "$BODY")"
else
  BODY="$(python3 - <<PY
import json
print(json.dumps({"expirationDateTime":"${EXPIRES_AT}"},separators=(',',':')))
PY
)"
  RESP="$(curl -sS -X PATCH "https://graph.microsoft.com/v1.0/subscriptions/${SUBSCRIPTION_ID}" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "$BODY")"
fi

echo "$RESP" | python3 -m json.tool

if [[ "$MODE" == "create" ]]; then
  NEW_ID="$(python3 - <<PY
import json
obj=json.loads('''${RESP}''')
print(obj.get('id',''))
PY
)"
  if [[ -n "$NEW_ID" ]]; then
    mkdir -p "$(dirname "$SUBSCRIPTION_STATE_FILE")"
    printf '%s\n' "$NEW_ID" > "$SUBSCRIPTION_STATE_FILE"
    echo "Saved subscription ID to $SUBSCRIPTION_STATE_FILE"
  fi
fi

echo "Done (${MODE}). Endpoint=${NOTIFICATION_URL}, expires=${EXPIRES_AT}"
