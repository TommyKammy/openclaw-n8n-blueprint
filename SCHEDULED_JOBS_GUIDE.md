# OpenClaw Scheduled Jobs System - Summary

## Scope

This guide describes how scheduled jobs work and how to operate them safely.
It intentionally does not claim current runtime state (active workflows, existing jobs, etc.).

## How Slack Users Can Create Scheduled Jobs

### Method 1: Via Slack Chat with OpenClaw

Users can ask OpenClaw in Slack to create scheduled jobs:

**Example conversation:**
```
User: @Claw Create a daily job to send me a summary at 9 AM
Claw: [Uses cron.add tool to create the job]
```

**Requirements:**
1. User must be in the allowed Slack user list (`SYNC_ALLOWED_SLACK_USER_IDS`)
2. User's Slack email must be verified and in the allowed list (`SYNC_ALLOWED_EMAILS`)
3. User must have an n8n account with matching email

### Method 2: Via OpenClaw CLI (Admin)

Admins can create jobs via CLI:

```bash
openclaw cron add \
  --name "My Daily Job" \
  --cron "0 9 * * *" \
  --tz "Asia/Tokyo" \
  --session isolated \
  --message "Your job description here" \
  --announce \
  --channel slack \
  --to "user:U0123456789"
```

### How It Works

1. **Job Creation**: Job is created in OpenClaw with `sessionTarget: isolated`
2. **Sync Detection**: Sync worker detects the job via `cron.list` API
3. **Requester Discovery**: Sync worker looks for who created the job in session files
4. **Workflow Creation**: Creates n8n workflow with Schedule Trigger
5. **Ownership**: Sets workflow owner to the requester's n8n account
6. **Activation**: Workflow is activated in n8n

### User Isolation & Security

- **Memory Isolation**: Each user gets isolated memory space
  - Path: `~/.openclaw/workspace/memory/users/{slack_user_id}/`
  - Jobs can only access their own memory directory
  
- **Workflow Ownership**: Workflows are owned by the user's n8n account
  - Linked via email address
  - User sees only their own workflows in n8n UI

- **Allowed Lists**: System restricts sync to specific users only
  - Configured via `SYNC_ALLOWED_SLACK_USER_IDS` and `SYNC_ALLOWED_EMAILS`

## Technical Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────┐
│   Slack User    │────▶│  OpenClaw Gateway │────▶│  Cron Jobs  │
└─────────────────┘     └──────────────────┘     └─────────────┘
                               │                          │
                               ▼                          ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────┐
│   n8n Workflow  │◀────│  Sync Worker     │◀────│  Shared Vol │
└─────────────────┘     └──────────────────┘     └─────────────┘
```

## Files Modified

1. `/home/tommy/Dev/openclaw-n8n-blueprint/docker-compose.prod.yml`
   - Removed read_only from openclaw-gateway
   - Removed conflicting tmpfs mounts

2. `/home/tommy/Dev/openclaw-n8n-blueprint/docker/openclaw/openclaw.json`
   - Changed bind from "loopback" to "lan"

3. `/home/tommy/Dev/openclaw-n8n-blueprint/docker/sync/openclaw_n8n_sync_worker.py`
   - Fixed JSON parsing to handle UI output
   - Uses explicit gateway connection flags when env vars are set

## Current Issue

**Existing jobs may be skipped** with reason "no_requester_found" because:
- Jobs were created from host CLI, not from Slack conversation
- Sync worker cannot determine which Slack user created them

**Solution**: 
- Re-create jobs through Slack/OpenClaw, OR
- Manually update job metadata to include requester info

## Testing the System

To test creating a job from Slack:

1. Open Slack and mention @Claw in a DM or channel
2. Say: "Schedule a daily job to check my email at 8 AM"
3. OpenClaw should create the job and it will sync to n8n within 60 seconds
4. Check n8n UI for the new workflow

## Configuration Reference

Key environment variables in `.env`:
```bash
SYNC_ALLOWED_SLACK_USER_IDS=U0123456789
SYNC_ALLOWED_EMAILS=your-email@example.com
SYNC_USER_EMAIL_MAP=U0123456789=your-email@example.com
SYNC_INTERVAL_SECONDS=60
```

## Next Steps

1. Test job creation from Slack
2. Verify workflows execute correctly
3. Monitor newsletter delivery
4. Add more users to allowed lists as needed
