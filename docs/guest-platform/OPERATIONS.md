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

After import:

1. Set webhook paths and credentials.
2. Set active mode only after test payloads pass.
3. Add operator Slack channel IDs in workflow variables.

## Test Matrix

- Request intake webhook with duplicate payloads (idempotency check).
- Repo factory on a test slug.
- PR event notification with sample GitHub webhook payload.
- Deploy callback notification with success and failure payloads.
- Daily audit dry run with missing optional APIs.

## Operational Notes (No Vercel Account Yet)

- Keep deploy workflow callback active.
- Mark deployment status as `pending_vercel_setup` in Slack until account is ready.
- Do not block repo bootstrap or PR loop on Vercel setup.
