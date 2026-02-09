# Systemd units

This folder contains sample systemd unit files for running the stack reliably after a host reboot.

## Install

1) Copy the unit into `/etc/systemd/system/`:

```bash
sudo cp -a /home/tommy/Dev/openclaw-n8n-blueprint/scripts/systemd/openclaw-n8n-stack.service /etc/systemd/system/openclaw-n8n-stack.service
```

2) Reload + enable:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now openclaw-n8n-stack.service
```

## Verify

```bash
sudo systemctl status openclaw-n8n-stack.service
sudo docker compose -f /home/tommy/Dev/openclaw-n8n-blueprint/docker-compose.prod.yml ps
sudo ss -lntp | egrep ':(80|443)\\s'
```
