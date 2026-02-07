# Guest Platform Incident Runbook

## Incident Types

1. Repository created with wrong permissions
2. PR merged without required checks
3. Wrong guest received notification
4. Secret leakage or token compromise
5. Deployment callback failures

## Immediate Actions

### 1) Stop automation safely

- Disable affected n8n workflows (do not delete).
- If needed, stop only `slack-provisioner` or webhook endpoints via nginx route toggle.

### 2) Contain scope

- Identify impacted guest repo(s).
- Revoke or rotate impacted credentials.
- Temporarily lock affected repositories.

### 3) Recover service

- Re-run repo bootstrap for affected guest using scripts.
- Re-apply branch protection.
- Replay webhook from captured payload with corrected routing.

## Standard Recovery Commands

```bash
# Re-apply branch protection
./scripts/guest-platform/configure_branch_protection.sh <owner/repo>

# Re-set required secrets
./scripts/guest-platform/register_guest_app.sh <guest-slug> <app-slug>
```

## Verification Checklist

- Correct repo and branch protection active.
- Required checks are enforced before merge.
- Slack messages route only to expected guest channel.
- No plaintext secrets in logs or git history.

## Postmortem Requirements

- Timeline of incident and detection.
- Root cause and prevention change.
- Token rotation confirmation.
- Runbook update if process gap found.
