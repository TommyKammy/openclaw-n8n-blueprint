# Guest Platform Scripts

## Core Scripts

- `register_guest_app.sh` - create private repo, configure branch protection (best effort), set secrets, set PR webhook.
- `full_guest_automation.py` - end-to-end guest onboarding automation.
- `full_guest_automation_service.py` - webhook API wrapper around `full_guest_automation.py`.

## Full Automation Flow

`full_guest_automation.py` performs:

1. Create/reuse Slack channel `app-dev-<guest-slug>`.
2. Invite `@Claw` and guest user to channel.
3. Set channel topic/purpose with repository naming convention.
4. Post and pin prompt-template examples (on channel create by default).
5. Create private repo from `GUEST_TEMPLATE_REPO` under `GITHUB_OWNER`.
6. Apply repo bootstrap (`register_guest_app.sh`).
7. Create/reuse Vercel project and set `VERCEL_PROJECT_ID` secret.
8. Push author-linked empty commit to trigger initial deployment.

## Required Environment Variables

- `SLACK_BOT_TOKEN`
- `CLAW_BOT_USER_ID`
- `GITHUB_OWNER`
- `GUEST_TEMPLATE_REPO`
- `GITHUB_TOKEN` (used by `gh`)
- `VERCEL_TOKEN`
- `VERCEL_ORG_ID`

Optional:

- `SLACK_ADMIN_USER_TOKEN` (for workspace invites by email)
- `VERCEL_GIT_COMMIT_AUTHOR_NAME`
- `VERCEL_GIT_COMMIT_AUTHOR_EMAIL`

Service variables:

- `GUEST_AUTOMATION_HOST`
- `GUEST_AUTOMATION_PORT`
- `GUEST_AUTOMATION_TOKEN`
- `POST_PROMPT_TEMPLATES_MODE` (`on_create` or `always`)

## Example

```bash
./scripts/guest-platform/full_guest_automation.py \
  --guest-name "Bob" \
  --guest-email "bob@example.com" \
  --app-slug "bob-app"
```

## Notes

- Slack workspace invite requires admin-capable token/scopes and may vary by Slack plan.
- The script is idempotent for channel/repo/project creation where APIs support reuse checks.
