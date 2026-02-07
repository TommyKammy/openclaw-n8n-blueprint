# Guest Platform Security Model

## Core Principles

- Least privilege for all tokens and service credentials.
- Per-repository isolation for guest apps.
- Explicit approval/merge policy, no fake proxy approvals.
- No cross-guest data access.

## Identity and Access

- Slack requester identity is validated through provisioner mapping.
- GitHub automation identity is a dedicated bot token or GitHub App.
- n8n uses dedicated API keys and rotates them periodically.

## Repository Isolation

- One private repository per guest app.
- Main branch protection required:
  - pull requests required
  - at least one approving review
  - status checks required
  - force push disabled

## Secret Management

- Host-level secrets in `.env` or secret manager.
- Guest app runtime secrets in GitHub repo secrets only.
- Never commit secrets to git.

## Data Isolation

- Preferred: database per guest app.
- If shared database is unavoidable:
  - every domain table includes `tenant_id`
  - all query paths enforce tenant filter
  - tenant access tests are mandatory

## Slack and Webhook Security

- Verify Slack signatures on inbound requests.
- Protect n8n callbacks with bearer token.
- Use idempotency keys for webhook processing.

## Logging and Audit

- Audit log records for provisioning, approval, and merge actions.
- Deployment callback status history retained in n8n.
- Failed auth/access attempts are monitored and alerted.

## Rotation Policy

- Rotate GitHub token every 90 days.
- Rotate webhook tokens every 90 days or on incident.
- Rotate Slack signing secret and bot token on compromise.
