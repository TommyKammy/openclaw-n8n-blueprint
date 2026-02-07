# OpenClaw + n8n Enterprise Blueprint

Production-ready blueprint for running:

- n8n + PostgreSQL
- OpenClaw gateway
- OpenClaw -> n8n sync worker
- Slack + Microsoft Teams guest auto-provisioning into n8n
- Nginx TLS edge routing

This repository is designed for fast reproducibility on a new host.

## Architecture

- `nginx` is the public entrypoint (`80/443`)
- `n8n` is internal (`5678` in Docker network)
- `openclaw` exposes loopback gateway + hooks internally
- `slack_n8n_provisioner.py` handles Slack and Teams provisioning events
- `openclaw_n8n_sync_worker.py` syncs eligible OpenClaw scheduled jobs into n8n workflows

## Key Features

- Slack and Teams guest provisioning into n8n using a single provisioner service
- OpenClaw -> n8n workflow sync with requester allowlists and ownership assignment
- Per-user memory/session isolation for chat operations
- Health and metrics endpoints for both provisioning and sync services
- Hardened production compose profile with security and resource controls

## Chat History Isolation

- Slack and Teams chat histories are separated per user by design.
- OpenClaw session scope is configured to isolate direct-message context per sender (`per-sender` + `per-channel-peer`).
- Synced OpenClaw workflows also inject a memory isolation policy and user-scoped session key, so persistent memory paths remain user-specific.
- This prevents one guest from seeing or reusing another guest's conversational memory by default.

## Main Endpoints

- `/` -> n8n UI/API
- `/webhook/*` -> n8n webhooks (public)
- `/openclaw-hooks/*` -> OpenClaw hooks
- `/slack/events` -> Slack Events API intake
- `/teams/events` -> Microsoft Graph notifications intake
- `/slack/provisioner/healthz` -> provisioner health
- `/sync-worker/healthz` -> sync worker health
- `/sync-worker/metrics` -> sync worker metrics (Prometheus text format)

## Repository Layout

- `docker-compose.yml` - baseline deployment
- `docker-compose.prod.yml` - hardened profile
- `docker/nginx/n8n.conf` - edge routing
- `docker/openclaw/` - OpenClaw image + config template
- `docker/provisioner/` - provisioning service image
- `docker/sync/` - sync worker image and code
- `slack_n8n_provisioner.py` - Slack/Teams to n8n provisioning service
- `scripts/teams/` - Graph subscription create/renew helpers
- `scripts/guest-platform/` - guest repository bootstrap/protection scripts
- `n8n/workflows/guest-platform/` - importable guest platform workflows
- `docs/guest-platform/` - operations, security model, and incident runbook
- `SETUP-GUIDE.md` - detailed setup/ops notes

## Quick Start

1. Copy and edit env file:

```bash
cp .env.example .env
```

2. Place TLS cert files:

- `certs/fullchain.pem`
- `certs/privkey.pem`

3. Build and run (baseline):

```bash
docker compose up -d --build
```

4. Or hardened profile:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

5. Verify:

```bash
docker compose ps
curl -I https://<your-domain>/slack/provisioner/healthz
curl -I https://<your-domain>/sync-worker/healthz
curl -s https://<your-domain>/sync-worker/metrics
```

## Required Environment Variables

At minimum set these in `.env`:

- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `N8N_HOST`, `WEBHOOK_URL`, `N8N_ENCRYPTION_KEY`
- `OPENCLAW_GATEWAY_TOKEN`
- `OPENCLAW_HOOK_URL`, `OPENCLAW_HOOK_TOKEN`
- `SLACK_SIGNING_SECRET`, `SLACK_BOT_TOKEN`
- `N8N_API_KEY`, `N8N_BASE_URL`
- `SYNC_ALLOWED_SLACK_USER_IDS`, `SYNC_ALLOWED_EMAILS`

Optional Teams provisioning vars:

- `TEAMS_ENABLED=true`
- `TEAMS_CLIENT_STATE=<secret>`
- `ALLOWED_TEAMS_TENANT_IDS=<tenant-id[,tenant-id2]>`
- `TEAMS_REQUIRE_GUEST_ONLY=true`

## Teams Graph Subscription

Use helper script:

```bash
MODE=create ./scripts/teams/create_or_renew_graph_subscription.sh
```

Auto-renew templates are under:

- `scripts/teams/systemd/teams-graph-subscription-renew.service`
- `scripts/teams/systemd/teams-graph-subscription-renew.timer`

Full details: `scripts/teams/README.md`

## Security Notes

- Never commit real secrets to git.
- Rotate all tokens/keys before production rollout.
- Keep firewall minimal and expose only nginx publicly.
- Treat Docker socket mounts as privileged access.

## License

Internal project template. Add your organization license policy before public distribution.
