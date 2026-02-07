#!/usr/bin/env python3
import hmac
import hashlib
import json
import os
import secrets
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
    HOST = os.environ.get("PROVISIONER_HOST", "127.0.0.1")
    PORT = int(os.environ.get("PROVISIONER_PORT", "18089"))
    DB_PATH = os.environ.get("PROVISIONER_DB_PATH", "/var/lib/slack-n8n-provisioner/provisioner.db")

    AUTO_PROVISION_ENABLED = env_bool("AUTO_PROVISION_ENABLED", False)
    REQUIRE_SLACK_EMAIL_VERIFICATION = env_bool("REQUIRE_SLACK_EMAIL_VERIFICATION", True)

    ALLOWED_SLACK_TEAM_IDS = {x.strip() for x in os.environ.get("ALLOWED_SLACK_TEAM_IDS", "").split(",") if x.strip()}
    ALLOWED_EMAIL_DOMAINS = {x.strip().lower() for x in os.environ.get("ALLOWED_EMAIL_DOMAINS", "").split(",") if x.strip()}

    SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET", "")
    SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")

    # Microsoft Teams / Microsoft Graph webhook mode
    TEAMS_ENABLED = env_bool("TEAMS_ENABLED", False)
    TEAMS_CLIENT_STATE = os.environ.get("TEAMS_CLIENT_STATE", "")
    ALLOWED_TEAMS_TENANT_IDS = {x.strip() for x in os.environ.get("ALLOWED_TEAMS_TENANT_IDS", "").split(",") if x.strip()}
    TEAMS_REQUIRE_GUEST_ONLY = env_bool("TEAMS_REQUIRE_GUEST_ONLY", True)

    N8N_BASE_URL = os.environ.get("N8N_BASE_URL", "https://n8n.example.com")
    N8N_API_KEY = os.environ.get("N8N_API_KEY", "")
    N8N_USER_CREATE_PATH = os.environ.get("N8N_USER_CREATE_PATH", "/api/v1/users")

    ONBOARDING_MODE = os.environ.get("ONBOARDING_MODE", "setup_link")
    ONBOARDING_SETUP_LINK = os.environ.get("ONBOARDING_SETUP_LINK", "https://n8n.example.com/signin")

    GOG_ACCOUNT = os.environ.get("GOG_ACCOUNT", "oc.w.kawada@gmail.com")
    GOG_KEYRING_PASSWORD = os.environ.get("GOG_KEYRING_PASSWORD", "")
    GOG_SEND_TIMEOUT = int(os.environ.get("GOG_SEND_TIMEOUT", "25"))


CFG = Config()


def now_epoch():
    return int(time.time())


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def init_db(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
              id TEXT PRIMARY KEY,
              provider TEXT NOT NULL,
              received_at INTEGER NOT NULL,
              event_type TEXT,
              payload TEXT NOT NULL,
              status TEXT NOT NULL,
              attempts INTEGER NOT NULL DEFAULT 0,
              reason TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mappings (
              provider TEXT NOT NULL,
              external_user_id TEXT NOT NULL,
              tenant_or_team_id TEXT,
              email TEXT,
              n8n_user_id TEXT,
              status TEXT NOT NULL,
              updated_at INTEGER NOT NULL,
              reason TEXT,
              PRIMARY KEY(provider, external_user_id)
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def db_exec(query, params=(), fetch=False):
    conn = sqlite3.connect(CFG.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(query, params)
        rows = cur.fetchall() if fetch else None
        conn.commit()
        return rows
    finally:
        conn.close()


def upsert_mapping(provider, external_user_id, tenant_or_team_id, email, n8n_user_id, status, reason=""):
    db_exec(
        """
        INSERT INTO mappings (provider, external_user_id, tenant_or_team_id, email, n8n_user_id, status, updated_at, reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(provider, external_user_id) DO UPDATE SET
          tenant_or_team_id=excluded.tenant_or_team_id,
          email=excluded.email,
          n8n_user_id=excluded.n8n_user_id,
          status=excluded.status,
          updated_at=excluded.updated_at,
          reason=excluded.reason
        """,
        (provider, external_user_id, tenant_or_team_id, email, n8n_user_id, status, now_epoch(), reason),
    )


def enqueue_event(event_id, provider, event_type, payload):
    try:
        db_exec(
            "INSERT INTO events (id, provider, received_at, event_type, payload, status) VALUES (?, ?, ?, ?, ?, 'pending')",
            (event_id, provider, now_epoch(), event_type, json.dumps(payload, ensure_ascii=True)),
        )
        return True
    except sqlite3.IntegrityError:
        return False


def verify_slack_signature(raw_body, ts, sig):
    if not CFG.SLACK_SIGNING_SECRET:
        return False
    if not ts or not sig:
        return False
    try:
        ts_int = int(ts)
    except ValueError:
        return False
    if abs(now_epoch() - ts_int) > 300:
        return False
    base = f"v0:{ts}:{raw_body.decode('utf-8')}".encode("utf-8")
    digest = hmac.new(CFG.SLACK_SIGNING_SECRET.encode("utf-8"), base, hashlib.sha256).hexdigest()
    expected = f"v0={digest}"
    return hmac.compare_digest(expected, sig)


def call_slack_users_info(user_id):
    if not CFG.SLACK_BOT_TOKEN:
        return None
    req = urllib.request.Request("https://slack.com/api/users.info", data=urllib.parse.urlencode({"user": user_id}).encode("utf-8"), method="POST")
    req.add_header("Authorization", f"Bearer {CFG.SLACK_BOT_TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            if not payload.get("ok"):
                return None
            return payload.get("user", {})
    except Exception:
        return None


def n8n_create_user(email):
    if not CFG.N8N_API_KEY:
        raise RuntimeError("missing N8N_API_KEY")
    payload = [{"email": email}]
    url = CFG.N8N_BASE_URL.rstrip("/") + CFG.N8N_USER_CREATE_PATH
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("X-N8N-API-KEY", CFG.N8N_API_KEY)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            out = json.loads(resp.read().decode("utf-8"))
            if isinstance(out, list) and out:
                user = out[0].get("user", {})
                return {
                    "id": user.get("id") or "created",
                    "inviteAcceptUrl": user.get("inviteAcceptUrl"),
                    "created": True,
                }
            return {"id": "created", "inviteAcceptUrl": None, "created": True}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        if e.code in (409, 422):
            return {"id": "exists", "inviteAcceptUrl": None, "created": False}
        raise RuntimeError(f"n8n create user failed: {e.code} {body[:300]}")


def send_onboarding_email(email, invite_url=None):
    setup_link = invite_url or CFG.ONBOARDING_SETUP_LINK
    if CFG.ONBOARDING_MODE == "setup_link":
        body = (
            "Welcome to n8n.\n\n"
            "Your enterprise chat guest account has been provisioned.\n"
            f"Please set up/sign in here: {setup_link}\n\n"
            "If you cannot sign in, contact the administrator."
        )
    else:
        temp_password = secrets.token_urlsafe(12)
        body = (
            "Welcome to n8n.\n\n"
            f"Temporary password: {temp_password}\n"
            "Please change it immediately after first login."
        )

    cmd = [
        "gog",
        "--account",
        CFG.GOG_ACCOUNT,
        "--no-input",
        "gmail",
        "send",
        "--to",
        email,
        "--subject",
        "n8n account onboarding",
        "--body",
        body,
        "--plain",
    ]
    env = os.environ.copy()
    if CFG.GOG_KEYRING_PASSWORD:
        env["GOG_KEYRING_PASSWORD"] = CFG.GOG_KEYRING_PASSWORD
    res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=CFG.GOG_SEND_TIMEOUT)
    if res.returncode != 0:
        raise RuntimeError(f"gog send failed: {res.stderr.strip()[:300]}")


def domain_allowed(email):
    if not CFG.ALLOWED_EMAIL_DOMAINS:
        return True
    domain = email.split("@")[-1]
    return domain in CFG.ALLOWED_EMAIL_DOMAINS


def process_slack_event(row):
    payload = json.loads(row["payload"])
    team_id = payload.get("team_id") or payload.get("team", {}).get("id")
    event = payload.get("event", {})
    user = event.get("user", event)
    slack_user_id = user.get("id")
    if not slack_user_id:
        db_exec("UPDATE events SET status='denied', reason=? WHERE id=?", ("missing_user_id", row["id"]))
        return

    if CFG.ALLOWED_SLACK_TEAM_IDS and team_id not in CFG.ALLOWED_SLACK_TEAM_IDS:
        upsert_mapping("slack", slack_user_id, team_id, None, None, "denied", "team_not_allowed")
        db_exec("UPDATE events SET status='denied', reason=? WHERE id=?", ("team_not_allowed", row["id"]))
        return

    slack_user = call_slack_users_info(slack_user_id) if CFG.REQUIRE_SLACK_EMAIL_VERIFICATION else user
    if CFG.REQUIRE_SLACK_EMAIL_VERIFICATION and not slack_user:
        db_exec("UPDATE events SET status='failed', attempts=attempts+1, reason=? WHERE id=?", ("slack_verify_failed", row["id"]))
        return

    safe_user = slack_user or {}

    is_guest = bool(safe_user.get("is_restricted") or safe_user.get("is_ultra_restricted"))
    if not is_guest:
        upsert_mapping("slack", slack_user_id, team_id, None, None, "denied", "user_not_guest")
        db_exec("UPDATE events SET status='denied', reason=? WHERE id=?", ("user_not_guest", row["id"]))
        return

    email = (safe_user.get("profile", {}).get("email") or "").strip().lower()
    if not email:
        upsert_mapping("slack", slack_user_id, team_id, None, None, "denied", "email_missing")
        db_exec("UPDATE events SET status='denied', reason=? WHERE id=?", ("email_missing", row["id"]))
        return
    if not domain_allowed(email):
        upsert_mapping("slack", slack_user_id, team_id, email, None, "denied", "domain_not_allowed")
        db_exec("UPDATE events SET status='denied', reason=? WHERE id=?", ("domain_not_allowed", row["id"]))
        return

    if not CFG.AUTO_PROVISION_ENABLED:
        upsert_mapping("slack", slack_user_id, team_id, email, None, "dry_run", "auto_provision_disabled")
        db_exec("UPDATE events SET status='done', reason=? WHERE id=?", ("dry_run", row["id"]))
        return

    created = n8n_create_user(email)
    send_onboarding_email(email, created.get("inviteAcceptUrl"))
    status = "created" if created.get("created") else "exists"
    upsert_mapping("slack", slack_user_id, team_id, email, created.get("id"), status, "ok")
    db_exec("UPDATE events SET status='done', reason=? WHERE id=?", ("provisioned", row["id"]))


def process_teams_event(row):
    payload = json.loads(row["payload"])
    items = payload.get("value", []) if isinstance(payload, dict) else []
    if not items:
        db_exec("UPDATE events SET status='denied', reason=? WHERE id=?", ("missing_items", row["id"]))
        return

    # Process first valid event in this notification batch.
    item = items[0]
    tenant_id = item.get("tenantId") or item.get("organizationId") or ""
    if CFG.ALLOWED_TEAMS_TENANT_IDS and tenant_id not in CFG.ALLOWED_TEAMS_TENANT_IDS:
        db_exec("UPDATE events SET status='denied', reason=? WHERE id=?", ("tenant_not_allowed", row["id"]))
        return

    resource = item.get("resourceData", {}) if isinstance(item.get("resourceData"), dict) else {}
    external_user_id = resource.get("id") or item.get("resource") or "unknown"
    user_type = (resource.get("userType") or "").strip().lower()
    if CFG.TEAMS_REQUIRE_GUEST_ONLY and user_type and user_type != "guest":
        upsert_mapping("teams", external_user_id, tenant_id, None, None, "denied", "user_not_guest")
        db_exec("UPDATE events SET status='denied', reason=? WHERE id=?", ("user_not_guest", row["id"]))
        return

    email = (resource.get("mail") or resource.get("userPrincipalName") or "").strip().lower()
    if not email:
        upsert_mapping("teams", external_user_id, tenant_id, None, None, "denied", "email_missing")
        db_exec("UPDATE events SET status='denied', reason=? WHERE id=?", ("email_missing", row["id"]))
        return
    if not domain_allowed(email):
        upsert_mapping("teams", external_user_id, tenant_id, email, None, "denied", "domain_not_allowed")
        db_exec("UPDATE events SET status='denied', reason=? WHERE id=?", ("domain_not_allowed", row["id"]))
        return

    if not CFG.AUTO_PROVISION_ENABLED:
        upsert_mapping("teams", external_user_id, tenant_id, email, None, "dry_run", "auto_provision_disabled")
        db_exec("UPDATE events SET status='done', reason=? WHERE id=?", ("dry_run", row["id"]))
        return

    created = n8n_create_user(email)
    send_onboarding_email(email, created.get("inviteAcceptUrl"))
    status = "created" if created.get("created") else "exists"
    upsert_mapping("teams", external_user_id, tenant_id, email, created.get("id"), status, "ok")
    db_exec("UPDATE events SET status='done', reason=? WHERE id=?", ("provisioned", row["id"]))


def process_event(row):
    provider = row["provider"]
    if provider == "slack":
        process_slack_event(row)
    elif provider == "teams":
        process_teams_event(row)
    else:
        db_exec("UPDATE events SET status='denied', reason=? WHERE id=?", ("unknown_provider", row["id"]))


def worker_loop():
    while True:
        rows = db_exec(
            "SELECT id, provider, payload FROM events WHERE status IN ('pending','failed') AND attempts < 5 ORDER BY received_at ASC LIMIT 10",
            fetch=True,
        ) or []
        for row in rows:
            try:
                process_event(row)
            except Exception as exc:
                db_exec("UPDATE events SET status='failed', attempts=attempts+1, reason=? WHERE id=?", (str(exc)[:500], row["id"]))
        time.sleep(2)


class Handler(BaseHTTPRequestHandler):
    def _json(self, code, payload):
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _text(self, code, text):
        body = text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/healthz":
            self._json(200, {"ok": True, "time": now_iso()})
            return
        if self.path.startswith("/teams/events"):
            # Microsoft Graph validation handshake
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            token = (params.get("validationToken") or [""])[0]
            if token:
                self._text(200, token)
                return
        self._json(404, {"ok": False, "error": "not_found"})

    def do_POST(self):
        if self.path == "/slack/events":
            self._handle_slack()
            return
        if self.path.startswith("/teams/events"):
            self._handle_teams()
            return
        self._json(404, {"ok": False, "error": "not_found"})

    def _handle_slack(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            self._json(400, {"ok": False, "error": "invalid_json"})
            return

        if payload.get("type") == "url_verification":
            self._text(200, payload.get("challenge", ""))
            return

        ts = self.headers.get("X-Slack-Request-Timestamp", "")
        sig = self.headers.get("X-Slack-Signature", "")
        if not verify_slack_signature(raw, ts, sig):
            self._json(401, {"ok": False, "error": "invalid_signature"})
            return

        event_type = payload.get("event", {}).get("type")
        if event_type not in {"team_join", "user_change"}:
            self._json(200, {"ok": True, "ignored": True})
            return
        event_id = payload.get("event_id") or secrets.token_hex(16)
        queued = enqueue_event(event_id, "slack", event_type, payload)
        self._json(200, {"ok": True, "queued": queued})

    def _handle_teams(self):
        if not CFG.TEAMS_ENABLED:
            self._json(403, {"ok": False, "error": "teams_disabled"})
            return

        qs = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(qs)
        token = (params.get("validationToken") or [""])[0]
        if token:
            self._text(200, token)
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            self._json(400, {"ok": False, "error": "invalid_json"})
            return

        if CFG.TEAMS_CLIENT_STATE:
            values = payload.get("value", []) if isinstance(payload, dict) else []
            if values:
                cs = values[0].get("clientState", "")
                if cs != CFG.TEAMS_CLIENT_STATE:
                    self._json(401, {"ok": False, "error": "invalid_client_state"})
                    return

        event_id = f"teams-{secrets.token_hex(12)}"
        queued = enqueue_event(event_id, "teams", "graph_notification", payload)
        self._json(202, {"ok": True, "queued": queued})

    def log_message(self, format, *args):
        return


def main():
    init_db(CFG.DB_PATH)
    t = threading.Thread(target=worker_loop, daemon=True)
    t.start()
    server = ThreadingHTTPServer((CFG.HOST, CFG.PORT), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
