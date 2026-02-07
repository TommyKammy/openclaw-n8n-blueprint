# Teams Graph Subscription Helper

This folder contains a helper script to create or renew a Microsoft Graph webhook subscription
for Teams/Entra guest provisioning events.

## File

- `create_or_renew_graph_subscription.sh`

## Required env vars

- `TENANT_ID`
- `GRAPH_CLIENT_ID`
- `GRAPH_CLIENT_SECRET`
- `PUBLIC_BASE_URL` (e.g. `https://n8n-s-app01.tmcast.net`)
- `TEAMS_CLIENT_STATE` (must match your provisioner env)

## Create subscription

```bash
MODE=create \
TENANT_ID=<tenant-id> \
GRAPH_CLIENT_ID=<app-id> \
GRAPH_CLIENT_SECRET=<secret> \
PUBLIC_BASE_URL=https://n8n.example.com \
TEAMS_CLIENT_STATE=<client-state-secret> \
./scripts/teams/create_or_renew_graph_subscription.sh
```

By default it subscribes to:
- `resource=/users`
- `changeType=updated`
- `expirationDateTime=now+48h`

## Renew subscription

```bash
MODE=renew \
TENANT_ID=<tenant-id> \
GRAPH_CLIENT_ID=<app-id> \
GRAPH_CLIENT_SECRET=<secret> \
PUBLIC_BASE_URL=https://n8n.example.com \
TEAMS_CLIENT_STATE=<client-state-secret> \
SUBSCRIPTION_ID=<subscription-id> \
./scripts/teams/create_or_renew_graph_subscription.sh
```

If `SUBSCRIPTION_ID` is omitted, it will read from `./scripts/teams/subscription-id.txt`.

## Notes

- Endpoint used: `https://<domain>/teams/events`
- Ensure `TEAMS_ENABLED=true` in your provisioner env.
- Ensure your Graph app has application permissions for the selected resource.

## Auto-renew with systemd timer

Templates are provided under `scripts/teams/systemd`.

1. Copy blueprint to host path (example):

```bash
sudo mkdir -p /opt
sudo cp -a /home/tommy/Dev/openclaw-n8n-blueprint /opt/openclaw-n8n-blueprint
```

2. Install env file:

```bash
sudo cp /opt/openclaw-n8n-blueprint/scripts/teams/renew-subscription.env.example /etc/default/teams-graph-subscription-renew
sudo chmod 600 /etc/default/teams-graph-subscription-renew
```

3. Install systemd unit + timer:

```bash
sudo cp /opt/openclaw-n8n-blueprint/scripts/teams/systemd/teams-graph-subscription-renew.service /etc/systemd/system/
sudo cp /opt/openclaw-n8n-blueprint/scripts/teams/systemd/teams-graph-subscription-renew.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now teams-graph-subscription-renew.timer
```

4. Run once immediately:

```bash
sudo systemctl start teams-graph-subscription-renew.service
sudo systemctl status teams-graph-subscription-renew.service --no-pager
```

5. Check timer schedule:

```bash
systemctl list-timers --all | grep teams-graph-subscription-renew
```
