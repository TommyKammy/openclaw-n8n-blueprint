# Guest Platform Current Spec (Validated)

Last validated: 2026-02-08

This document captures the currently implemented and verified behavior of the guest app development platform built on this blueprint.

## 1) Runtime Topology

- Control plane is hosted on the OpenClaw + n8n blueprint stack.
- `n8n` receives webhooks and runs guest platform workflows.
- `openclaw-gateway` handles chat-side generation/routing.
- GitHub repositories are provisioned from a template and managed by scripts under `scripts/guest-platform/`.
- Deployments are executed via GitHub Actions in each guest repository and sent to Vercel.
- Deploy status is sent back to n8n and then to Slack.

## 2) Canonical Repositories

- Blueprint repository: `TommyKammy/openclaw-n8n-blueprint`
- Template repository (template=true): `TommyKammy/guest-app-template`
- First validated guest repo: `TommyKammy/demo-app-dev-demo`

## 3) Verified End-to-End Flows

### A. PR Notification Flow

1. PR opened/synchronized on guest repo.
2. GitHub webhook (`pull_request`) calls n8n `guest_pr_review_gate`.
3. n8n posts PR notification to Slack approval channel.

Status: validated with HTTP 200 deliveries and successful workflow executions.

### B. Merge/Deploy/Notify Flow

1. PR merged to `main`.
2. Guest repo Deploy workflow runs migrations and Vercel deploy.
3. Workflow sends callback to `guest_deploy_notify` webhook.
4. n8n posts deploy status to Slack.

Status: validated with successful Deploy workflow and successful n8n callback execution.

## 4) n8n Workflow Contract

### Active workflows

- `guest_request_intake`
- `guest_repo_factory`
- `guest_pr_review_gate`
- `guest_deploy_notify`
- `guest_platform_daily_audit`

### Webhook production URLs

- PR gate: `https://n8n-s-app01.tmcast.net/webhook/guest-platform/pr-review-gate`
- Deploy callback: `https://n8n-s-app01.tmcast.net/webhook/guest-deploy-callback`
- Intake: `https://n8n-s-app01.tmcast.net/webhook/guest-platform/request-intake`
- Repo factory: `https://n8n-s-app01.tmcast.net/webhook/guest-platform/repo-factory`

### Important implementation detail

- Webhook nodes include explicit `webhookId` values in exported JSON.
- Without persisted `webhookId`, production webhook registration can become unstable after API-based imports.

## 5) Slack Channel Contract

- Approval channel: `#guest-approval` (ID-based config recommended)
- Operator channel: `#operator-alert` (ID-based config recommended)
- Example guest channel: `#app-dev-demo`

Notes:

- Use channel IDs in env (`C...`) for reliability.
- Bot must be invited to each target channel.

## 6) GitHub Automation Contract

Scripts in `scripts/guest-platform/`:

- `register_guest_app.sh`: full bootstrap entrypoint.
- `create_guest_repo.sh`: creates private repo from template.
- `set_repo_secrets.sh`: writes runtime/deploy secrets.
- `configure_repo_webhook.sh`: creates or updates PR webhook (idempotent).
- `configure_branch_protection.sh`: applies branch protection or skips gracefully if plan disallows it.

Branch protection behavior:

- On plans where private-repo protection is unavailable, script logs a safe skip instead of failing whole bootstrap.

## 7) Deploy Workflow Contract (Guest Repos)

Current expected behavior in template deploy workflow:

1. Install dependencies.
2. Run Drizzle migration (`db:migrate`).
3. Set default status (`pending_vercel_setup`).
4. If Vercel secrets exist, run `vercel pull/build/deploy`.
5. POST callback to n8n with final status/url.

Required repository secrets:

- `DATABASE_URL`
- `DIRECT_URL`
- `N8N_DEPLOY_CALLBACK_URL`
- `N8N_DEPLOY_CALLBACK_TOKEN`
- `VERCEL_TOKEN`
- `VERCEL_ORG_ID`
- `VERCEL_PROJECT_ID`

## 8) n8n Environment Security Constraint

Observed setting: `N8N_BLOCK_ENV_ACCESS_IN_NODE` blocks `$env` in Function nodes.

Operational consequence:

- Workflows that depend on `$env` inside Function node code will fail.
- Current live workflows were adjusted to avoid blocked env access in those nodes.

Recommendation:

- Prefer credentials/Set nodes/HTTP node fields for secrets and constants.
- Avoid direct `$env` reads in Function node code when env access is blocked.

## 9) Known Limitations

- Private repo branch protection may be unavailable depending on GitHub plan.
- Vercel deployment identity can depend on commit author metadata and team access rules.
- Repo factory workflow is currently operator-assisted for command execution safety in n8n.

## 10) Repeatable Onboarding Checklist

1. Ensure template repo is marked `is_template=true`.
2. Run:

```bash
./scripts/guest-platform/register_guest_app.sh <guest-slug> <app-slug> "<description>"
```

3. Create guest channel in Slack (`#app-dev-<guest-slug>`), invite bot and guest.
4. Open PR in guest repo and confirm PR notification.
5. Merge PR and confirm deploy callback notification.
