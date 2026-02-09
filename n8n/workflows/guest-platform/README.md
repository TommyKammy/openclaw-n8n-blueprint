# Guest Platform n8n Workflows

These workflows are import-ready templates aligned with `App_Development_Platform_for_Guest-Implementation_Plan-v2.md`.

## Included Workflows

- `guest_request_intake.json`
- `guest_repo_factory.json`
- `guest_pr_review_gate.json`
- `guest_deploy_notify.json`
- `guest_platform_daily_audit.json`
- `guest_full_onboarding.json`

## Import Steps

1. n8n UI -> Workflows -> Import from File.
2. Import each JSON file.
3. Configure credentials and environment variables.
4. Activate after test payload validation.

## Required Environment Variables in n8n

- `GITHUB_OWNER`
- `GITHUB_TOKEN` (or use GitHub credential nodes)
- `N8N_DEPLOY_CALLBACK_TOKEN`
- `SLACK_GUEST_APPROVAL_CHANNEL`
- `SLACK_OPERATOR_ALERT_CHANNEL`

Optional (until Vercel is available):

- `VERCEL_TOKEN`
- `VERCEL_ORG_ID`

For PR webhook ingestion:

- `N8N_PR_WEBHOOK_URL`
- `GITHUB_WEBHOOK_SECRET`

For full onboarding webhook automation:

- Set `guest_full_onboarding` node values:
  - `automation_url` (reachable URL for `full_guest_automation_service.py`)
  - `automation_token`
  - `operator_channel`
  - `slack_token`
- Recommended in Docker: `automation_url=http://host.docker.internal:18111/guest-platform/full-onboard`
  and add `host.docker.internal:host-gateway` to the n8n container `extra_hosts`.

For offboarding webhook automation:

- `OFFBOARDING_TOKEN`
- `N8N_BASE_URL`
- `N8N_API_KEY`

Security notes:

- `guest_full_onboarding` validates `Authorization: Bearer <FULL_ONBOARDING_TOKEN>`.
- `guest_offboarding` validates `Authorization: Bearer <OFFBOARDING_TOKEN>`.
- Do not hardcode Slack/GitHub/Vercel/n8n tokens in Set/IF nodes.
- Prefer `$vars.*` (n8n Variables) for runtime secrets if `$env` access is restricted in your n8n setup.
