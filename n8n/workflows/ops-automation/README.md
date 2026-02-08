# Ops Automation Workflows

Import these workflows to let OpenClaw operate daily checks and incident response with n8n execution.

## Included

- `ops_daily_health_check.json`
- `ops_incident_triage.json`
- `ops_auto_repair_safe.json`
- `ops_human_approval_gate.json`

## Required n8n Environment Variables

- `SLACK_BOT_TOKEN`
- `SLACK_OPERATOR_ALERT_CHANNEL`
- `N8N_BASE_URL`
- `N8N_API_KEY`
- `OPS_AUTOMATION_SHARED_TOKEN`
- `OPS_APPROVER_SLACK_USER_IDS`

## Notes

- Function nodes intentionally avoid direct `$env` access to support environments with `N8N_BLOCK_ENV_ACCESS_IN_NODE`.
- Keep webhooks active in production mode.
