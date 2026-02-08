# Ops Automation (OpenClaw Operator)

This document defines the operational automation layer where OpenClaw acts as the operator and n8n executes daily checks, triage, safe auto-repair, and approval-gated actions.

## Objectives

- Detect platform issues early.
- Triage incidents into actionable categories.
- Auto-run only low-risk repairs.
- Require human approval for risky operations.
- Keep operator visibility in Slack.

## Workflows

- `ops_daily_health_check` (scheduled)
  - Verifies n8n API health.
  - Posts daily health summary to operator channel.

- `ops_incident_triage` (webhook)
  - Accepts incident payloads from OpenClaw/tools.
  - Classifies severity/category and emits runbook-aligned next actions.
  - Posts triage summary to operator channel.

- `ops_auto_repair_safe` (webhook)
  - Validates shared automation token.
  - Performs safe actions (workflow reactivation) when `workflow_ids` are provided.
  - Posts execution results to operator channel.

- `ops_human_approval_gate` (webhook)
  - Creates approval tickets for risky actions.
  - Processes explicit approve/reject decisions.
  - Posts approval outcomes to operator channel.

## Endpoints

- `POST /webhook/ops/incident-triage`
- `POST /webhook/ops/auto-repair-safe`
- `POST /webhook/ops/human-approval-gate`

## Command Matrix

- `daily-check`
  - Trigger: schedule.
  - Action: API health check + Slack summary.
  - Risk: low.

- `triage`
  - Trigger: webhook payload (`source`, `error`, `status`, `context`).
  - Action: severity + category + recommended actions.
  - Risk: low.

- `safe-repair`
  - Trigger: webhook payload with `workflow_ids`.
  - Action: deactivate/activate specified workflows.
  - Risk: low/medium.

- `approval-gate`
  - Trigger: webhook payload with `request_id`, `operation`, `requested_by`.
  - Action: pending -> approved/rejected state announcement.
  - Risk: medium/high.

## Escalation Policy

- `sev=critical`
  - Immediate Slack alert in operator channel.
  - OpenClaw posts urgent remediation checklist.
  - Human approval required before risky changes.

- `sev=high`
  - Auto-triage + safe-repair allowed.
  - Escalate to human if safe-repair fails once.

- `sev=medium/low`
  - Auto-triage with recommendations.
  - Human intervention optional.

## Required Environment Variables

- `SLACK_BOT_TOKEN`
- `SLACK_OPERATOR_ALERT_CHANNEL`
- `N8N_BASE_URL`
- `N8N_API_KEY`
- `OPS_AUTOMATION_SHARED_TOKEN`
- `OPS_APPROVER_SLACK_USER_IDS` (comma-separated Slack user IDs)

## Security Rules

- Never expose `OPS_AUTOMATION_SHARED_TOKEN` outside secured runtime.
- Keep risky operations behind `ops_human_approval_gate`.
- Use ID-based channel/user checks, not display names.
