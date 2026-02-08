#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return re.sub(r"^-+|-+$", "", slug)


def http_post_json(url: str, payload: dict, headers: dict | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def slack_api(method: str, payload: dict, token: str) -> dict:
    url = f"https://slack.com/api/{method}"
    return http_post_json(url, payload, {"Authorization": f"Bearer {token}"})


def ensure_channel(channel_name: str, bot_token: str) -> tuple[str, bool]:
    res = slack_api("conversations.create", {"name": channel_name, "is_private": False}, bot_token)
    if res.get("ok"):
        return res["channel"]["id"], True
    if res.get("error") == "name_taken":
        list_res = slack_api(
            "conversations.list",
            {"types": "public_channel,private_channel", "exclude_archived": True, "limit": 1000},
            bot_token,
        )
        if list_res.get("ok"):
            for ch in list_res.get("channels", []):
                if ch.get("name") == channel_name:
                    return ch["id"], False
    raise RuntimeError(f"failed to create/find channel {channel_name}: {res}")


def lookup_user_id_by_email(email: str, token: str) -> str | None:
    res = slack_api("users.lookupByEmail", {"email": email}, token)
    if res.get("ok"):
        return res["user"]["id"]
    return None


def invite_user_to_workspace(email: str, admin_token: str) -> None:
    # Requires Slack admin-level token/scopes.
    res = slack_api("admin.users.invite", {"email": email}, admin_token)
    if not res.get("ok") and res.get("error") not in {"already_invited", "already_in_team", "already_in_workspace"}:
        raise RuntimeError(f"failed to invite user to workspace: {res}")


def invite_to_channel(channel_id: str, user_ids: list[str], bot_token: str) -> None:
    user_ids = [u for u in user_ids if u]
    if not user_ids:
        return
    res = slack_api("conversations.invite", {"channel": channel_id, "users": ",".join(user_ids)}, bot_token)
    if not res.get("ok") and res.get("error") not in {
        "already_in_channel",
        "cant_invite_self",
        "user_is_bot",
        "invalid_users",
    }:
        raise RuntimeError(f"failed to invite users to channel: {res}")


def set_channel_context(channel_id: str, guest_slug: str, bot_token: str) -> None:
    topic = f"Guest app development for {guest_slug}. Repo naming: {guest_slug}-<app-slug>."
    purpose = (
        f"Build and iterate apps for guest {guest_slug}. "
        "Use the prompt templates from @Claw and keep app_slug lowercase-hyphen format."
    )
    topic_res = slack_api("conversations.setTopic", {"channel": channel_id, "topic": topic}, bot_token)
    if not topic_res.get("ok"):
        raise RuntimeError(f"failed to set channel topic: {topic_res}")
    purpose_res = slack_api("conversations.setPurpose", {"channel": channel_id, "purpose": purpose}, bot_token)
    if not purpose_res.get("ok"):
        raise RuntimeError(f"failed to set channel purpose: {purpose_res}")


def build_prompt_template_message(guest_slug: str) -> str:
    return "\n".join(
        [
            "*Welcome to your app-dev channel*",
            f"Repository naming convention: `{guest_slug}-<app-slug>`",
            "Use lowercase letters, numbers, and hyphens only for `app_slug`.",
            "",
            "*Prompt examples*",
            "1) Create app",
            f"`Create app app_slug=booking for {guest_slug}. Use repo name {guest_slug}-booking. Include auth, responsive UI, and deployment-ready setup.`",
            "2) Add feature",
            f"`In repo {guest_slug}-booking, add calendar sync. Include tests and update README.`",
            "3) Fix bug",
            f"`In repo {guest_slug}-booking, fix timezone issue in booking confirmation and add regression test.`",
            "4) Deploy check",
            f"`Check latest deploy status for {guest_slug}-booking and summarize failures with next steps.`",
        ]
    )


def post_and_pin_prompt_templates(channel_id: str, guest_slug: str, bot_token: str) -> str:
    msg = build_prompt_template_message(guest_slug)
    post_res = slack_api("chat.postMessage", {"channel": channel_id, "text": msg}, bot_token)
    if not post_res.get("ok"):
        raise RuntimeError(f"failed to post template message: {post_res}")
    ts = post_res.get("ts", "")
    if ts:
        pin_res = slack_api("pins.add", {"channel": channel_id, "timestamp": ts}, bot_token)
        if not pin_res.get("ok") and pin_res.get("error") != "already_pinned":
            raise RuntimeError(f"failed to pin template message: {pin_res}")
    return ts


def set_repo_secret(repo: str, key: str, value: str) -> None:
    if not value:
        return
    subprocess.run(["gh", "secret", "set", key, "--repo", repo, "--body", value], check=True)


def create_vercel_project(repo_name: str, team_id: str, vercel_token: str) -> str:
    url = f"https://api.vercel.com/v10/projects?teamId={urllib.parse.quote(team_id)}"
    payload = {
        "name": repo_name,
        "framework": "nextjs",
        "buildCommand": "npm run build",
        "devCommand": "npm run dev",
        "installCommand": "npm install",
    }
    try:
        res = http_post_json(url, payload, {"Authorization": f"Bearer {vercel_token}"})
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        if e.code == 409:
            query = f"https://api.vercel.com/v9/projects/{urllib.parse.quote(repo_name)}?teamId={urllib.parse.quote(team_id)}"
            req = urllib.request.Request(query, headers={"Authorization": f"Bearer {vercel_token}"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                existing = json.loads(resp.read().decode("utf-8"))
            return existing["id"]
        raise RuntimeError(f"failed to create vercel project: {e.code} {body[:400]}")
    return res["id"]


def trigger_author_linked_deploy(repo_https: str, branch: str, author_name: str, author_email: str) -> None:
    with tempfile.TemporaryDirectory(prefix="guest-auto-") as tmpdir:
        subprocess.run(["git", "clone", repo_https, tmpdir], check=True)
        subprocess.run(["git", "checkout", branch], cwd=tmpdir, check=True)
        subprocess.run(
            ["git", "commit", "--allow-empty", "--author", f"{author_name} <{author_email}>", "-m", "Trigger initial deployment"],
            cwd=tmpdir,
            check=True,
        )
        subprocess.run(["git", "push", "origin", branch], cwd=tmpdir, check=True)


def run_register_script(guest_slug: str, app_slug: str, description: str, env: dict) -> str:
    script = Path(__file__).parent / "register_guest_app.sh"
    subprocess.run([str(script), guest_slug, app_slug, description], check=True, env=env)
    owner = env.get("GITHUB_OWNER", "TommyKammy")
    return f"{owner}/{guest_slug}-{app_slug}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Fully automate guest onboarding: Slack + GitHub + Vercel")
    parser.add_argument("--guest-name", required=True)
    parser.add_argument("--guest-email", required=False)
    parser.add_argument("--guest-slack-user-id", required=False)
    parser.add_argument("--app-slug", required=True)
    parser.add_argument("--description", default="Guest app repository")
    parser.add_argument("--skip-workspace-invite", action="store_true")
    args = parser.parse_args()

    env = os.environ.copy()
    bot_token = env.get("SLACK_BOT_TOKEN", "")
    claw_bot_user_id = env.get("CLAW_BOT_USER_ID", "")
    admin_token = env.get("SLACK_ADMIN_USER_TOKEN", "")
    vercel_token = env.get("VERCEL_TOKEN", "")
    vercel_org_id = env.get("VERCEL_ORG_ID", "")
    vercel_author_name = env.get("VERCEL_GIT_COMMIT_AUTHOR_NAME", "Tomoaki Kawada")
    vercel_author_email = env.get("VERCEL_GIT_COMMIT_AUTHOR_EMAIL", "tomoaki.w.kawada@gmail.com")
    post_templates_mode = env.get("POST_PROMPT_TEMPLATES_MODE", "on_create").strip().lower()

    if not bot_token:
        raise RuntimeError("SLACK_BOT_TOKEN is required")

    guest_slug = slugify(args.guest_name)
    app_slug = slugify(args.app_slug)
    if not guest_slug or not app_slug:
        raise RuntimeError("guest/app slug resolution failed")

    channel_name = f"app-dev-{guest_slug}"
    channel_id, channel_created = ensure_channel(channel_name, bot_token)

    guest_user_id = args.guest_slack_user_id
    if not guest_user_id and args.guest_email:
        guest_user_id = lookup_user_id_by_email(args.guest_email, bot_token)

    if not guest_user_id and args.guest_email and not args.skip_workspace_invite and admin_token:
        invite_user_to_workspace(args.guest_email, admin_token)
        guest_user_id = lookup_user_id_by_email(args.guest_email, bot_token)

    invite_candidates = [claw_bot_user_id, guest_user_id]
    invite_to_channel(channel_id, [u for u in invite_candidates if isinstance(u, str)], bot_token)
    set_channel_context(channel_id, guest_slug, bot_token)

    template_message_ts = ""
    should_post_templates = post_templates_mode == "always" or (post_templates_mode == "on_create" and channel_created)
    if should_post_templates:
        template_message_ts = post_and_pin_prompt_templates(channel_id, guest_slug, bot_token)

    full_repo = run_register_script(guest_slug, app_slug, args.description, env)

    if vercel_token and vercel_org_id:
        repo_name = full_repo.split("/")[-1]
        vercel_project_id = create_vercel_project(repo_name, vercel_org_id, vercel_token)
        set_repo_secret(full_repo, "VERCEL_PROJECT_ID", vercel_project_id)
        repo_https = f"https://github.com/{full_repo}.git"
        trigger_author_linked_deploy(repo_https, "main", vercel_author_name, vercel_author_email)

    print(
        json.dumps(
            {
                "ok": True,
                "guest_slug": guest_slug,
                "channel_name": channel_name,
                "channel_id": channel_id,
                "channel_created": channel_created,
                "repo": full_repo,
                "guest_user_id": guest_user_id,
                "template_message_ts": template_message_ts,
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
