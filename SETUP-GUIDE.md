# OpenClaw + n8n Repro Setup Guide

This guide is organization-agnostic and covers reproducible deployment for:

- n8n + PostgreSQL
- OpenClaw gateway
- OpenClaw -> n8n sync worker
- Guest provisioning from Slack and/or Microsoft Teams
- Nginx TLS edge routing

It supports three usage patterns:

1. Slack-only organizations
2. Teams-only organizations
3. Hybrid Slack + Teams organizations

## 1. Target architecture

- `n8n` + `postgres` run in Docker.
- `openclaw` runs in Docker.
- `slack-n8n-provisioner` runs in Docker (handles Slack and Teams ingestion).
- `openclaw-n8n-sync-worker` runs in Docker.
- `nginx` terminates TLS and routes:
  - `/` -> n8n
  - `/webhook/*` -> n8n
  - `/openclaw-hooks/*` -> OpenClaw hooks
  - `/slack/events` -> Slack provisioning intake
  - `/teams/events` -> Teams provisioning intake
  - `/slack/provisioner/healthz` -> provisioner health
  - `/sync-worker/healthz` and `/sync-worker/metrics` -> sync worker health/metrics

## 2. Prerequisites (all organizations)

- Linux host (Ubuntu recommended), Docker Engine, Docker Compose plugin.
- Public DNS record pointing to the host.
- TLS cert/key (`certs/fullchain.pem`, `certs/privkey.pem`) or ACME automation.
- Outbound internet access from containers to:
  - Slack API (if Slack enabled)
  - Microsoft Graph (if Teams enabled)
  - n8n domain URL
  - Gmail API (`gog`) for onboarding email
- Firewall policy permitting only required inbound ports (`80/443` + SSH).

## 3. Identity provider prerequisites

### 3.1 Slack organizations (optional)

- Slack app for OpenClaw chat (Socket mode) if Slack chat is used.
- Slack app (or dedicated app) for provisioning events with:
  - `users:read`
  - `users:read.email`
- Event Subscriptions enabled for:
  - `team_join`
  - `user_change`
- Request URL:
  - `https://<domain>/slack/events`

### 3.2 Teams organizations (optional)

- Microsoft Entra app with Graph app permissions suitable for chosen subscription resource.
- Graph webhook endpoint:
  - `https://<domain>/teams/events`
- `clientState` secret configured and matched in `.env`.
- Subscription create/renew workflow (scripts provided under `scripts/teams`).

## 4. Pre-deploy planning checklist

Before deployment, define:

- Tenant/workspace allowlists:
  - `ALLOWED_SLACK_TEAM_IDS`
  - `ALLOWED_TEAMS_TENANT_IDS`
- Guest policy:
  - Slack guest only (built-in)
  - Teams guest only (`TEAMS_REQUIRE_GUEST_ONLY=true`)
- Email domain policy (`ALLOWED_EMAIL_DOMAINS`) if needed.
- n8n onboarding mode (`ONBOARDING_MODE=setup_link` recommended).
- Secret management approach (vault/secret manager preferred over plain files).

## 5. Blueprint files

- `docker-compose.yml` (baseline)
- `docker-compose.prod.yml` (hardened)
- `docker/openclaw/Dockerfile`
- `docker/provisioner/Dockerfile`
- `docker/sync/Dockerfile`
- `docker/sync/openclaw_n8n_sync_worker.py`
- `docker/nginx/n8n.conf`
- `.env.example`
- `slack_n8n_provisioner.py`
- `scripts/teams/create_or_renew_graph_subscription.sh`
- `scripts/teams/renew-subscription.sh`

## 6. Deploy (baseline)

1. Copy env template and fill values:

```bash
cp .env.example .env
```

2. Place TLS files under `certs/`.

3. Build and start:

```bash
docker compose up -d --build
```

4. Validate:

```bash
docker compose ps
curl -I https://your-n8n-domain.example
curl -I https://your-n8n-domain.example/slack/provisioner/healthz
curl -I https://your-n8n-domain.example/sync-worker/healthz
curl -s https://your-n8n-domain.example/sync-worker/metrics
docker compose logs --tail=50 openclaw-sync-worker
```

5. Channel-specific validation:

- Slack orgs: verify Slack Event Subscription URL with `/slack/events`.
- Teams orgs: verify Graph validation handshake on `/teams/events`.

## 7. Deploy (hardened production)

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Hardened profile includes:

- read-only root filesystem where possible
- `no-new-privileges`
- healthchecks
- tmpfs for runtime scratch
- CPU/memory/pid limits
- local-only exposure except nginx

## 8. Critical runtime settings

- OpenClaw DM/session isolation:
  - `session.scope=per-sender`
  - `session.dmScope=per-channel-peer`
- OpenClaw hooks enabled with token.
- Sync worker interval and allowlist policy:
  - `SYNC_INTERVAL_SECONDS`
  - `SYNC_ALLOWED_SLACK_USER_IDS`
  - `SYNC_ALLOWED_EMAILS`
  - `SYNC_REQUIRE_SLACK_EMAIL_VERIFICATION`
- Provisioning service requires valid:
  - `N8N_API_KEY`
  - `GOG_ACCOUNT`
  - `GOG_KEYRING_PASSWORD`
- Slack mode requires:
  - `SLACK_SIGNING_SECRET`
  - `SLACK_BOT_TOKEN`
- Teams mode requires:
  - `TEAMS_ENABLED=true`
  - `TEAMS_CLIENT_STATE`
  - `ALLOWED_TEAMS_TENANT_IDS`

## 9. Data, backup, and recovery

- Persist volumes:
  - `n8n_postgres_data`
  - `n8n_app_data`
  - `openclaw_state`
  - `slack_provisioner_data`
  - `sync_state`
- Use host-side backup jobs for n8n DB and n8n app data.
- Keep off-host backup copies and test restore drills regularly.

## 10. Microsoft Teams enterprise notes

- Endpoint for Graph notifications:
  - `https://<domain>/teams/events`
- Validation handshake (`validationToken`) is supported.
- Configure `clientState` to match `TEAMS_CLIENT_STATE`.
- Use helper scripts:
  - `scripts/teams/create_or_renew_graph_subscription.sh`
  - `scripts/teams/renew-subscription.sh`
- Auto-renew templates:
  - `scripts/teams/systemd/teams-graph-subscription-renew.service`
  - `scripts/teams/systemd/teams-graph-subscription-renew.timer`

## 11. Security notes

- Never commit `.env` with real secrets.
- Rotate all secrets before cloning to another host/org.
- Keep inbound firewall minimal (`80/443` + SSH).
- `openclaw-sync-worker` mounts `/var/run/docker.sock`; treat as privileged.
- Prefer separate Slack app for provisioning if isolation of duties is required.
- Monitor provisioning + sync logs for denial/error spikes.
