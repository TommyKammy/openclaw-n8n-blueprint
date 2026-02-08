# Session Handoff

Last updated: 2026-02-08

Use this file to quickly recover platform context in a new chat/session.

## Current Scope

- OpenClaw + n8n blueprint is operational as the guest app control plane.
- Guest platform automation is implemented and validated.
- OpenClaw operator workflows (daily ops + incident response) are implemented and validated.

## Key Repositories

- Blueprint: `TommyKammy/openclaw-n8n-blueprint`
- Template: `TommyKammy/guest-app-template` (template repo enabled)
- Demo guest repo: `TommyKammy/demo-app-dev-demo`

## Production Webhook Endpoints

- Guest PR gate: `https://n8n-s-app01.tmcast.net/webhook/guest-platform/pr-review-gate`
- Guest deploy callback: `https://n8n-s-app01.tmcast.net/webhook/guest-deploy-callback`
- Guest intake: `https://n8n-s-app01.tmcast.net/webhook/guest-platform/request-intake`
- Guest repo factory: `https://n8n-s-app01.tmcast.net/webhook/guest-platform/repo-factory`
- Ops triage: `https://n8n-s-app01.tmcast.net/webhook/ops/incident-triage`
- Ops safe repair: `https://n8n-s-app01.tmcast.net/webhook/ops/auto-repair-safe`
- Ops approval gate: `https://n8n-s-app01.tmcast.net/webhook/ops/human-approval-gate`

## Slack Channels

- Approval channel: `#guest-approval`
- Operator channel: `#operator-alert`
- Example guest channel: `#app-dev-demo`

Recommended: use channel IDs in env vars for reliability.

## n8n Workflows (Expected Active)

Guest platform:

- `guest_request_intake`
- `guest_repo_factory`
- `guest_pr_review_gate`
- `guest_deploy_notify`
- `guest_platform_daily_audit`

Ops automation:

- `ops_daily_health_check`
- `ops_incident_triage`
- `ops_auto_repair_safe`
- `ops_human_approval_gate`

## Required Runtime Inputs (Local/.env, Not in Git)

- GitHub: owner/token/webhook secret
- n8n: base URL + API key
- Slack: bot token + channel IDs
- Guest deploy callbacks: URL + token
- Vercel: token/org/project IDs
- Neon: database URLs
- Ops automation: shared token + approver Slack IDs

Do not store real secrets in repository files.

## Known Constraints

- Private-repo branch protection may be unavailable on current GitHub plan; automation handles safe skip.
- n8n can block env usage in Function nodes (`N8N_BLOCK_ENV_ACCESS_IN_NODE`), so workflow design avoids direct env access in Function logic when possible.
- Webhook nodes require stable `webhookId` in exports for reliable production registration.

## First 5 Checks in Any New Session

1. Verify webhooks return expected responses (`/webhook/...` endpoints).
2. Check latest n8n executions for guest + ops workflows.
3. Check latest GitHub Actions runs in template/guest repos.
4. Verify GitHub webhook delivery status is `200`.
5. Verify Slack bot can post to `#guest-approval` and `#operator-alert`.

## Primary References

- `docs/guest-platform/CURRENT_SPEC.md`
- `docs/guest-platform/OPS_AUTOMATION.md`
- `docs/guest-platform/OPERATIONS.md`
- `n8n/workflows/guest-platform/`
- `n8n/workflows/ops-automation/`
