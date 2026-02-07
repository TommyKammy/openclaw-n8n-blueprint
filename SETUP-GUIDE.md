# OpenClaw + n8n Repro Setup Guide

This guide captures the current working architecture and gives a repeatable deployment baseline for a new host.

## 1. Target architecture

- `n8n` + `postgres` run in Docker.
- `openclaw` runs in Docker.
- `slack-n8n-provisioner` runs in Docker.
- The same provisioner handles Slack and Microsoft Teams enterprise provisioning.
- `openclaw-n8n-sync-worker` runs in Docker.
- `nginx` terminates TLS and routes:
  - `/` -> n8n
  - `/webhook/*` -> n8n
  - `/openclaw-hooks/*` -> OpenClaw hooks
  - `/slack/events` -> provisioner intake
  - `/teams/events` -> provisioner intake

## 2. Prerequisites

- Ubuntu host with Docker Engine + Compose plugin.
- DNS A record to host public IP.
- Valid TLS certificate and key files.
- Slack app for OpenClaw (Socket mode) and Slack app for provisioning (HTTP events).

## 3. Files in this blueprint

- `docker-compose.yml` (baseline)
- `docker-compose.prod.yml` (hardened)
- `docker/openclaw/Dockerfile`
- `docker/provisioner/Dockerfile`
- `docker/sync/Dockerfile`
- `docker/sync/openclaw_n8n_sync_worker.py`
- `docker/nginx/n8n.conf`
- `.env.example`
- `slack_n8n_provisioner.py` (Slack + Teams provisioning service)
- `scripts/teams/create_or_renew_graph_subscription.sh`

## 4. Deploy (baseline)

1. Copy `.env.example` to `.env` and fill all secrets.
2. Place TLS cert files under `certs/`:
   - `certs/fullchain.pem`
   - `certs/privkey.pem`
3. Build and run:

```bash
docker compose up -d --build
```

4. Check:

```bash
docker compose ps
curl -I https://your-n8n-domain.example
curl -I https://your-n8n-domain.example/slack/provisioner/healthz
curl -I https://your-n8n-domain.example/teams/events
curl -I https://your-n8n-domain.example/sync-worker/healthz
curl -s https://your-n8n-domain.example/sync-worker/metrics
docker compose logs --tail=50 openclaw-sync-worker
```

## 5. Deploy (hardened production)

Use the hardened compose file:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

The hardened profile adds:
- read-only root filesystem where possible
- `no-new-privileges`
- healthchecks
- tmpfs for runtime scratch
- explicit CPU/memory/pid limits
- local-only exposure except nginx

## 6. Data/backup guidance

- Persist volumes:
  - `n8n_postgres_data`
  - `n8n_app_data`
  - `openclaw_state`
  - `slack_provisioner_data`
- Add regular DB + app-data backups from host cron.

## 7. Critical runtime settings

- OpenClaw Slack memory isolation:
  - `session.scope = per-sender`
  - `session.dmScope = per-channel-peer`
- OpenClaw hooks enabled with token.
- Sync worker runs every `SYNC_INTERVAL_SECONDS` and enforces allowlists.
- Sync worker exposes:
  - `/sync-worker/healthz`
  - `/sync-worker/metrics` (Prometheus text format)
- Provisioner requires valid:
  - `SLACK_SIGNING_SECRET`
  - `SLACK_BOT_TOKEN`
  - `N8N_API_KEY`
- Teams mode (optional) requires:
  - `TEAMS_ENABLED=true`
  - `TEAMS_CLIENT_STATE`
  - `ALLOWED_TEAMS_TENANT_IDS`

## 9. Microsoft Teams enterprise provisioning notes

- Endpoint for Microsoft Graph change notifications:
  - `https://<domain>/teams/events`
- Validation handshake is supported via `validationToken` response.
- Configure Graph subscription with `clientState` matching `TEAMS_CLIENT_STATE`.
- Recommended resource: guest user lifecycle notifications from Entra ID / Graph.
- Helper script:
  - `scripts/teams/create_or_renew_graph_subscription.sh`
  - Usage details: `scripts/teams/README.md`
- Auto-renew templates:
  - `scripts/teams/renew-subscription.sh`
  - `scripts/teams/systemd/teams-graph-subscription-renew.service`
  - `scripts/teams/systemd/teams-graph-subscription-renew.timer`

## 8. Security notes

- Never commit `.env` with real secrets.
- Rotate all secrets before cloning this to another host.
- Keep inbound firewall minimal (`80/443` + SSH).
- `openclaw-sync-worker` mounts `/var/run/docker.sock`; treat this as privileged access and protect host access accordingly.
