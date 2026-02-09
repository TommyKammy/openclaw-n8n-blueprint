#!/usr/bin/env python3
import hmac
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def env_bool(name, default=False):
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    HOST = os.environ.get("GUEST_AUTOMATION_HOST", "0.0.0.0")
    PORT = int(os.environ.get("GUEST_AUTOMATION_PORT", "18111"))
    TOKEN = os.environ.get("GUEST_AUTOMATION_TOKEN", "")
    
    GITHUB_OWNER = os.environ.get("GITHUB_OWNER", "TommyKammy")
    GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
    GUEST_TEMPLATE_REPO = os.environ.get("GUEST_TEMPLATE_REPO", "TommyKammy/guest-app-template")
    
    SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
    CLAW_BOT_USER_ID = os.environ.get("CLAW_BOT_USER_ID", "U0ADFF3483E")
    
    VERCEL_TOKEN = os.environ.get("VERCEL_TOKEN", "")
    VERCEL_ORG_ID = os.environ.get("VERCEL_ORG_ID", "")

    DB_PATH = os.environ.get("GUEST_AUTOMATION_DB_PATH", "/var/lib/guest-automation/automation.db")


CFG = Config()


def init_db(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    con = sqlite3.connect(path)
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS slack_channels (
              channel_name TEXT PRIMARY KEY,
              channel_id TEXT NOT NULL,
              updated_at INTEGER NOT NULL
            )
            """
        )
        con.commit()
    finally:
        con.close()


def cache_slack_channel(channel_name, channel_id):
    if not channel_name or not channel_id:
        return
    con = sqlite3.connect(CFG.DB_PATH)
    try:
        con.execute(
            """
            INSERT INTO slack_channels (channel_name, channel_id, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(channel_name) DO UPDATE SET
              channel_id=excluded.channel_id,
              updated_at=excluded.updated_at
            """,
            (channel_name, channel_id, int(time.time())),
        )
        con.commit()
    finally:
        con.close()


def get_cached_slack_channel_id(channel_name):
    con = sqlite3.connect(CFG.DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT channel_id FROM slack_channels WHERE channel_name=? LIMIT 1",
            (channel_name,),
        ).fetchone()
        return row["channel_id"] if row else None
    finally:
        con.close()


def verify_token(auth_header):
    if not CFG.TOKEN:
        return True
    if not auth_header:
        return False
    expected = f"Bearer {CFG.TOKEN}"
    return hmac.compare_digest(auth_header, expected)


def create_github_repo(repo_name, description=""):
    if not CFG.GITHUB_TOKEN:
        return {"ok": False, "error": "missing GITHUB_TOKEN"}
    
    url = f"https://api.github.com/repos/{CFG.GUEST_TEMPLATE_REPO}/generate"
    headers = {
        "Authorization": f"Bearer {CFG.GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    }
    data = {
        "owner": CFG.GITHUB_OWNER,
        "name": repo_name,
        "description": description or f"Guest app for {repo_name}",
        "private": True,
        "include_all_branches": False
    }
    
    try:
        req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            return {"ok": True, "repo": f"{CFG.GITHUB_OWNER}/{repo_name}", "html_url": result.get("html_url")}
    except urllib.error.HTTPError as e:
        if e.code == 422:
            return {"ok": True, "repo": f"{CFG.GITHUB_OWNER}/{repo_name}", "html_url": f"https://github.com/{CFG.GITHUB_OWNER}/{repo_name}", "note": "repo_exists"}
        return {"ok": False, "error": f"github_error_{e.code}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def create_slack_channel(channel_name, guest_user_id):
    if not CFG.SLACK_BOT_TOKEN:
        return {"ok": False, "error": "missing SLACK_BOT_TOKEN"}
    
    # Create channel
    url = "https://slack.com/api/conversations.create"
    headers = {
        "Authorization": f"Bearer {CFG.SLACK_BOT_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {"name": channel_name, "is_private": False}
    
    try:
        def invite_users(channel_id, user_ids):
            # Invite each user individually to avoid partial failures.
            for uid in [str(u).strip() for u in (user_ids or []) if str(u).strip()]:
                invite_url = "https://slack.com/api/conversations.invite"
                invite_req = urllib.request.Request(
                    invite_url,
                    data=json.dumps({"channel": channel_id, "users": uid}).encode(),
                    headers=headers,
                    method="POST",
                )
                with urllib.request.urlopen(invite_req, timeout=10) as r:
                    out = json.loads(r.read().decode())
                if out.get("ok"):
                    continue
                if out.get("error") in {"already_in_channel", "cant_invite_self"}:
                    continue
                return {"ok": False, "error": out.get("error") or "invite_failed"}
            return {"ok": True}

        req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode())
            if not result.get("ok"):
                if result.get("error") == "name_taken":
                    cached = get_cached_slack_channel_id(channel_name)
                    if cached:
                        inv = invite_users(cached, [guest_user_id, CFG.CLAW_BOT_USER_ID])
                        if not inv.get("ok"):
                            return {"ok": False, "channel_id": cached, "channel_name": channel_name, "error": inv.get("error")}
                        return {"ok": True, "channel_id": cached, "channel_name": channel_name, "note": "cached"}
                    # Channel already exists, get its ID (requires read scopes)
                    existing = get_channel_id(channel_name)
                    if existing.get("ok"):
                        inv = invite_users(existing.get("channel_id"), [guest_user_id, CFG.CLAW_BOT_USER_ID])
                        if not inv.get("ok"):
                            return {"ok": False, "channel_id": existing.get("channel_id"), "channel_name": channel_name, "error": inv.get("error")}
                        existing["note"] = existing.get("note") or "existing"
                    return existing
                return {"ok": False, "error": result.get("error")}
            
            channel_id = result.get("channel", {}).get("id")
            cache_slack_channel(channel_name, channel_id)
            
            inv = invite_users(channel_id, [guest_user_id, CFG.CLAW_BOT_USER_ID])
            if not inv.get("ok"):
                return {"ok": False, "channel_id": channel_id, "channel_name": channel_name, "error": inv.get("error")}

            return {"ok": True, "channel_id": channel_id, "channel_name": channel_name}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def get_channel_id(channel_name):
    url = "https://slack.com/api/conversations.list"
    headers = {"Authorization": f"Bearer {CFG.SLACK_BOT_TOKEN}"}
    try:
        req = urllib.request.Request(f"{url}?types=public_channel,private_channel", headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode())
            if not result.get("ok"):
                return {"ok": False, "error": result.get("error") or "slack_error"}
            for channel in result.get("channels", []):
                if channel.get("name") == channel_name:
                    return {"ok": True, "channel_id": channel.get("id"), "channel_name": channel_name, "note": "existing"}
            return {"ok": False, "error": "channel_not_found"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def deploy_to_vercel(repo_name):
    if not CFG.VERCEL_TOKEN:
        return {"ok": True, "note": "vercel_not_configured"}
    if not CFG.VERCEL_ORG_ID:
        return {"ok": False, "error": "missing VERCEL_ORG_ID"}

    project_name = repo_name
    repo_full = f"{CFG.GITHUB_OWNER}/{repo_name}"

    base_qs = urllib.parse.urlencode({"teamId": CFG.VERCEL_ORG_ID})
    url = f"https://api.vercel.com/v9/projects?{base_qs}"
    headers = {
        "Authorization": f"Bearer {CFG.VERCEL_TOKEN}",
        "Content-Type": "application/json",
    }
    data = {
        "name": project_name,
        "gitRepository": {
            "type": "github",
            "repo": repo_full,
        },
    }

    def get_project():
        req = urllib.request.Request(
            "https://api.vercel.com/v9/projects/" + urllib.parse.quote(project_name) + "?" + base_qs,
            method="GET",
        )
        req.add_header("Authorization", f"Bearer {CFG.VERCEL_TOKEN}")
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def patch_project_link():
        req = urllib.request.Request(
            "https://api.vercel.com/v9/projects/" + urllib.parse.quote(project_name) + "?" + base_qs,
            data=json.dumps(
                {
                    "gitRepository": {
                        "type": "github",
                        "repo": repo_full,
                    }
                }
            ).encode("utf-8"),
            method="PATCH",
        )
        req.add_header("Authorization", f"Bearer {CFG.VERCEL_TOKEN}")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def create_deployment_from_git():
        if not CFG.GITHUB_TOKEN:
            return {"ok": False, "error": "missing GITHUB_TOKEN"}
        # Fetch repoId from GitHub (required by Vercel gitSource)
        gh_req = urllib.request.Request("https://api.github.com/repos/" + repo_full)
        gh_req.add_header("Authorization", f"Bearer {CFG.GITHUB_TOKEN}")
        gh_req.add_header("Accept", "application/vnd.github+json")
        with urllib.request.urlopen(gh_req, timeout=20) as r:
            gh = json.loads(r.read().decode("utf-8"))
        repo_id = gh.get("id")
        if not repo_id:
            return {"ok": False, "error": "github_repo_id_missing"}

        dep_url = "https://api.vercel.com/v13/deployments?" + base_qs
        payload = {
            "name": project_name,
            "project": project_name,
            "target": "production",
            "gitSource": {
                "type": "github",
                "repo": repo_full,
                "repoId": repo_id,
                "ref": "main",
            },
        }
        req = urllib.request.Request(dep_url, data=json.dumps(payload).encode("utf-8"), method="POST")
        req.add_header("Authorization", f"Bearer {CFG.VERCEL_TOKEN}")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                out = json.loads(resp.read().decode("utf-8"))
            return {"ok": True, "deployment_id": out.get("id"), "deployment_url": out.get("url")}
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")
            return {"ok": False, "error": f"vercel_deploy_error_{e.code}", "detail": body[:200]}

    # If project already exists, try to link it and deploy.
    try:
        existing = get_project()
        if isinstance(existing, dict) and existing.get("id"):
            linked = bool(existing.get("link") or existing.get("gitRepository"))
            if not linked:
                try:
                    patch_project_link()
                except Exception:
                    # We'll fall back to unlinked create below.
                    pass
            dep = create_deployment_from_git()
            if dep.get("ok"):
                return {
                    "ok": True,
                    "note": "deployed",
                    "project_id": existing.get("id"),
                    "project_name": project_name,
                    "repo": repo_full,
                    "deployment": dep,
                }
            # If deploy fails, still report project existence.
            return {
                "ok": True,
                "note": "project_exists_no_deploy",
                "project_id": existing.get("id"),
                "project_name": project_name,
                "repo": repo_full,
                "deployment": dep,
            }
    except Exception:
        pass

    try:
        req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            out = json.loads(resp.read().decode("utf-8"))
        return {
            "ok": True,
            "note": "created",
            "project_id": out.get("id"),
            "project_name": out.get("name") or project_name,
            "repo": repo_full,
        }
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")

        # Vercel requires the GitHub integration to be installed before you can
        # link projects to GitHub repos via the API. If it's missing, still
        # create the project (unlinked) so it shows up in the dashboard.
        if e.code == 400 and "install" in body.lower() and "github" in body.lower():
            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps({"name": project_name}).encode("utf-8"),
                    headers=headers,
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    out = json.loads(resp.read().decode("utf-8"))
                return {
                    "ok": True,
                    "note": "created_unlinked_install_github_app",
                    "project_id": out.get("id"),
                    "project_name": out.get("name") or project_name,
                    "repo": repo_full,
                    "warning": "vercel_github_integration_missing",
                }
            except Exception as exc:
                return {"ok": False, "error": f"vercel_create_unlinked_failed:{str(exc)[:200]}"}

        # If the project already exists, treat it as success.
        if e.code in (400, 409) and ("exists" in body.lower() or "already" in body.lower()):
            return {
                "ok": True,
                "note": "project_exists",
                "project_name": project_name,
                "repo": repo_full,
            }
        return {"ok": False, "error": f"vercel_error_{e.code}", "detail": body[:300]}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


class Handler(BaseHTTPRequestHandler):
    def _json(self, code, payload):
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path == "/guest-platform/full-onboard":
            self._handle_onboard()
            return
        self._json(404, {"ok": False, "error": "not_found"})

    def _handle_onboard(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        
        auth = self.headers.get("Authorization", "")
        if not verify_token(auth):
            self._json(401, {"ok": False, "error": "unauthorized"})
            return
        
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            self._json(400, {"ok": False, "error": "invalid_json"})
            return
        
        guest_name = payload.get("guest_name", "")
        guest_email = payload.get("guest_email", "")
        guest_slack_user_id = payload.get("guest_slack_user_id", "")
        app_slug = payload.get("app_slug", "starter-app")
        description = payload.get("description", f"Guest app for {guest_name}")
        
        if not guest_name or not guest_email:
            self._json(400, {"ok": False, "error": "missing_guest_name_or_email"})
            return
        
        # Generate names
        slug = re.sub(r"[^a-z0-9]+", "-", guest_name.lower()).strip("-")
        channel_name = f"app-dev-{slug}"
        repo_name = f"{slug}-{re.sub(r'[^a-z0-9]+', '-', app_slug.lower()).strip('-')}"
        
        # Execute automation steps
        results = {
            "ok": True,
            "guest_slug": guest_name,
            "channel_name": channel_name,
            "repo": f"{CFG.GITHUB_OWNER}/{repo_name}"
        }
        
        # 1. Create GitHub repo
        github_result = create_github_repo(repo_name, description)
        results["github"] = github_result
        if not github_result.get("ok"):
            results["ok"] = False
            results["error"] = github_result.get("error")
        
        # 2. Create Slack channel
        slack_result = create_slack_channel(channel_name, guest_slack_user_id)
        results["slack"] = slack_result
        if slack_result.get("ok"):
            results["channel_id"] = slack_result.get("channel_id")
        
        # 3. Deploy to Vercel (simplified)
        vercel_result = deploy_to_vercel(repo_name)
        results["vercel"] = vercel_result
        
        # Always respond 200 so upstream automation (n8n/provisioner) can
        # reliably parse the JSON body and decide how to handle failures.
        self._json(200, results)

    def log_message(self, format, *args):
        return


def main():
    init_db(CFG.DB_PATH)
    server = ThreadingHTTPServer((CFG.HOST, CFG.PORT), Handler)
    print(f"Guest automation service running on {CFG.HOST}:{CFG.PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
