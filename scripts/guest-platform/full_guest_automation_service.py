#!/usr/bin/env python3
import json
import os
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


HOST = os.environ.get("GUEST_AUTOMATION_HOST", "127.0.0.1")
PORT = int(os.environ.get("GUEST_AUTOMATION_PORT", "18111"))
TOKEN = os.environ.get("GUEST_AUTOMATION_TOKEN", "")
SCRIPT = Path(__file__).with_name("full_guest_automation.py")


class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/guest-platform/full-onboard":
            self._json(404, {"ok": False, "error": "not_found"})
            return

        auth = self.headers.get("Authorization", "")
        if not TOKEN or auth != f"Bearer {TOKEN}":
            self._json(401, {"ok": False, "error": "unauthorized"})
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            self._json(400, {"ok": False, "error": "invalid_json"})
            return

        guest_name = payload.get("guest_name")
        app_slug = payload.get("app_slug")
        if not guest_name or not app_slug:
            self._json(400, {"ok": False, "error": "missing_guest_or_app_slug"})
            return

        cmd = [
            str(SCRIPT),
            "--guest-name",
            str(guest_name),
            "--app-slug",
            str(app_slug),
            "--description",
            str(payload.get("description", "Guest app repository")),
        ]
        if payload.get("guest_email"):
            cmd += ["--guest-email", str(payload.get("guest_email"))]
        if payload.get("guest_slack_user_id"):
            cmd += ["--guest-slack-user-id", str(payload.get("guest_slack_user_id"))]
        if payload.get("skip_workspace_invite"):
            cmd += ["--skip-workspace-invite"]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True, env=os.environ.copy(), timeout=300)
            stdout = res.stdout.strip() or "{}"
            self._json(200, json.loads(stdout))
        except subprocess.CalledProcessError as e:
            self._json(500, {"ok": False, "error": "automation_failed", "detail": (e.stderr or e.stdout or "")[:1000]})
        except subprocess.TimeoutExpired:
            self._json(504, {"ok": False, "error": "timeout"})
        except Exception as e:
            self._json(500, {"ok": False, "error": "internal_error", "detail": str(e)[:500]})


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(json.dumps({"ok": True, "host": HOST, "port": PORT, "path": "/guest-platform/full-onboard"}, ensure_ascii=True), flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
