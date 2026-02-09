# OpenClaw N8N Platform - SSL & Data Persistence Setup

## ✅ SSL Certificate Configuration

### Certificate Status
- **Domain**: n8n-s-app01.tmcast.net
- **Type**: Let's Encrypt (Trusted SSL Certificate)
- **Issuer**: Let's Encrypt (E8)
- **Valid From**: Feb 7, 2026
- **Valid Until**: May 8, 2026
- **Auto-renewal**: Enabled (certbot will auto-renew before expiry)

### Auto-Renewal Hook
When certificates are renewed, nginx is automatically reloaded via:
- **Hook Location**: `/etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh`
- **Log**: `/var/log/letsencrypt/renewal-hooks.log`

## ✅ Data Persistence Configuration

All data is persisted using Docker volumes. When containers are stopped/removed, data remains intact:

### Volumes Used

1. **n8n_app_data** → `/home/node/.n8n`
   - Stores: Workflows, credentials, executions, settings
   - Container: n8n-app
   - Persists: YES

2. **n8n_postgres_data** → `/var/lib/postgresql/data`
   - Stores: n8n database (users, executions, workflow history)
   - Container: n8n-postgres
   - Persists: YES

3. **slack_provisioner_data** → `/var/lib/slack-n8n-provisioner`
   - Stores: Guest onboarding mappings, events database
   - Container: slack-n8n-provisioner
   - Persists: YES

4. **openclaw_state** → `/home/openclaw/.openclaw`
   - Stores: OpenClaw agent sessions and state
   - Container: openclaw-gateway
   - Persists: YES

5. **sync_state** → `/state`
   - Stores: Sync worker state
   - Container: openclaw-n8n-sync-worker
   - Persists: YES

## 🔒 SSL Verification

Test SSL certificate:
```bash
curl -v https://n8n-s-app01.tmcast.net 2>&1 | grep -E "SSL|TLS|certificate"
```

Expected output shows:
- TLSv1.3 handshake
- Certificate issued by Let's Encrypt
- Valid certificate chain

## 💾 Data Persistence Test

### To verify data persists after container restart:

1. **Check current workflows**:
```bash
sudo docker exec n8n-postgres psql -U n8n -d n8n -c "SELECT name, active FROM workflow_entity;"
```

2. **Stop containers**:
```bash
cd /home/tommy/Dev/openclaw-n8n-blueprint
sudo docker compose down
```

3. **Start containers**:
```bash
sudo docker compose up -d
```

4. **Verify workflows still exist**:
```bash
sudo docker exec n8n-postgres psql -U n8n -d n8n -c "SELECT name, active FROM workflow_entity;"
```

✅ **Result**: Workflows, user data, and all configurations will remain intact!

## 📋 Files Modified

1. **docker-compose.yml** - Updated SSL certificate paths to use Let's Encrypt
2. **docker-compose.prod.yml** - Updated SSL certificate paths for production
3. `/etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh` - Auto-reload nginx on cert renewal

## 🔐 Security Notes

- SSL certificates are automatically renewed by certbot
- Private keys are stored securely in `/etc/letsencrypt/live/`
- All data is persisted in Docker volumes (not container filesystem)
- Database credentials stored in `.env` file (never commit to git!)

## 🚀 Demo2 Onboarding Status

The infrastructure is now ready with:
- ✅ Valid SSL certificate (Let's Encrypt)
- ✅ Data persistence configured
- ✅ Onboarding workflow activated
- ✅ Off-boarding workflow activated
- ✅ Guest automation service running

You can now safely stop/start containers without losing any data!
