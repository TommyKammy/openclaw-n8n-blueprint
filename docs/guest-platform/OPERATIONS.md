# Guest Platform Operations

This runbook operates the guest app factory on top of the existing OpenClaw + n8n blueprint.

## Scope

- Slack guest request intake
- GitHub repo bootstrap from template
- PR approval notifications
- Deployment callback notifications
- Daily audit checks

## Preconditions

- `openclaw`, `n8n`, `slack-provisioner`, and `nginx` are healthy.
- A single primary sync runtime is selected (Docker sync worker recommended).
- `gh` is authenticated with permissions to create repos and manage secrets.

## Required Environment

- `GITHUB_OWNER` (example: `TommyKammy`)
- `GUEST_TEMPLATE_REPO` (example: `TommyKammy/guest-app-template`)
- `N8N_DEPLOY_CALLBACK_URL`
- `N8N_DEPLOY_CALLBACK_TOKEN`
- Optional while Vercel is pending: `VERCEL_TOKEN`, `VERCEL_ORG_ID`

## Provisioning a New Guest App

1. Validate guest mapping is present in provisioner DB.
2. Run repository bootstrap:

```bash
./scripts/guest-platform/register_guest_app.sh <guest-slug> <app-slug> "<description>"
```

3. Confirm repo created and branch protection enabled.
4. Confirm required secrets exist in repo.
5. Confirm PR webhook exists (if `N8N_PR_WEBHOOK_URL` and `GITHUB_WEBHOOK_SECRET` are set).

## Fully Automated Guest Onboarding

Use the full automation script to create Slack channel, invite users, create private GitHub repo from template, configure secrets/webhook, and bootstrap Vercel project:

```bash
./scripts/guest-platform/full_guest_automation.py \
  --guest-name "Bob" \
  --guest-email "bob@example.com" \
  --app-slug "bob-app"
```

Or run as API service and call via webhook payload:

```bash
python3 ./scripts/guest-platform/full_guest_automation_service.py
```

Endpoint:

- `POST /guest-platform/full-onboard`

## Vercel + Neon Onboarding

If Neon was created from Vercel console, prepare and set at least:

- `DATABASE_URL`
- `DIRECT_URL` (optional if your runtime only needs one URL)

Then rerun secret setup for an existing guest repo:

```bash
./scripts/guest-platform/set_repo_secrets.sh <owner/repo>
```

When Vercel project secrets are ready (`VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`), rerun the same script.

## n8n Workflows to Import

Import JSON files under `n8n/workflows/guest-platform/`:

- `guest_request_intake.json`
- `guest_repo_factory.json`
- `guest_pr_review_gate.json`
- `guest_deploy_notify.json`
- `guest_platform_daily_audit.json`
- `guest_full_onboarding.json`

After import:

1. Set webhook paths and credentials.
2. Set active mode only after test payloads pass.
3. Add operator Slack channel IDs in workflow variables.

## Ops Automation Workflows (OpenClaw Operator)

Import JSON files under `n8n/workflows/ops-automation/`:

- `ops_daily_health_check.json`
- `ops_incident_triage.json`
- `ops_auto_repair_safe.json`
- `ops_human_approval_gate.json`

Reference: `docs/guest-platform/OPS_AUTOMATION.md`

## Test Matrix

- Request intake webhook with duplicate payloads (idempotency check).
- Repo factory on a test slug.
- PR event notification with sample GitHub webhook payload.
- Deploy callback notification with success and failure payloads.
- Daily audit dry run with missing optional APIs.

## Operational Notes

- Source of truth for live validated behavior: `docs/guest-platform/CURRENT_SPEC.md`.
- Keep deploy callback active even when Vercel deploy is skipped/fails, so Slack receives status.
- Use channel IDs (not channel names) in env for stable Slack routing.
