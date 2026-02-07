#!/usr/bin/env python3
import glob
import hashlib
import json
import os
import re
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SLACK_FROM_RE = re.compile(r"Slack .* from ([A-Z0-9]+):")

SYNC_STATUS = {
    "ok": True,
    "last_run_at": None,
    "last_success_at": None,
    "last_error": "",
    "last_result": {"synced": 0, "deleted": 0, "managed": 0, "skipped": []},
}
LOCK = threading.Lock()


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)}\n{p.stderr.strip()}")
    return p.stdout


def env_bool(name, default=False):
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


def csv_set(name):
    raw = os.environ.get(name, "")
    return {x.strip().lower() for x in raw.split(",") if x.strip()}


def csv_set_raw(name):
    raw = os.environ.get(name, "")
    return {x.strip() for x in raw.split(",") if x.strip()}


def parse_email(text):
    m = EMAIL_RE.search(text or "")
    return m.group(0).lower() if m else None


def parse_slack_user_id(text):
    m = SLACK_FROM_RE.search(text or "")
    return m.group(1) if m else None


def content_text(content):
    if not isinstance(content, list):
        return ""
    out = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            out.append(item.get("text", ""))
    return "\n".join(out)


def discover_requesters(session_glob):
    requesters = {}
    for fp in sorted(glob.glob(session_glob), key=os.path.getmtime):
        last = {"slack_user_id": None, "email": None}
        with open(fp, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg = row.get("message", {})
                role = msg.get("role")
                if role == "user":
                    text = content_text(msg.get("content", []))
                    sid = parse_slack_user_id(text)
                    if sid:
                        last = {"slack_user_id": sid, "email": parse_email(text)}
                    continue
                if role != "toolResult" or msg.get("toolName") != "cron":
                    continue
                details = msg.get("details")
                if not isinstance(details, dict):
                    continue
                job_id = details.get("id")
                if job_id and last.get("slack_user_id"):
                    requesters[job_id] = dict(last)
    return requesters


def fetch_slack_email(bot_token, slack_user_id):
    if not bot_token:
        return None
    try:
        out = run([
            "curl",
            "-sS",
            "--max-time",
            "8",
            "https://slack.com/api/users.info",
            "-H",
            f"Authorization: Bearer {bot_token}",
            "--data-urlencode",
            f"user={slack_user_id}",
        ])
        data = json.loads(out)
        if not data.get("ok"):
            return None
        return (data.get("user", {}).get("profile", {}).get("email") or "").lower() or None
    except Exception:
        return None


def schedule_params(job):
    sch = job.get("schedule", {})
    kind = sch.get("kind")
    if kind == "cron" and sch.get("expr"):
        return {"rule": {"interval": [{"field": "cronExpression", "expression": sch["expr"]}]}}
    if kind == "every" and sch.get("everyMs"):
        mins = max(1, int(sch["everyMs"] / 60000))
        return {"rule": {"interval": [{"field": "minutes", "minutesInterval": mins}]}}
    return None


def workflow_id(job_id):
    return "ocsync" + hashlib.sha1(job_id.encode("utf-8")).hexdigest()[:30]


def isolation_message(original, slack_user_id, requester_email):
    root = f"~/.openclaw/workspace/memory/users/{slack_user_id}"
    who = requester_email or slack_user_id
    head = (
        "[Memory Isolation Policy]\n"
        f"Requester: {who}\n"
        f"Slack User ID: {slack_user_id}\n"
        f"Allowed memory root: {root}\n\n"
        "Rules:\n"
        "1. Read/write persistent memory only under the allowed memory root.\n"
        "2. Never read/write any other user's memory directory.\n"
        "3. If path is missing, create it only under the allowed root.\n"
        "4. Refuse requests for other users' memory.\n"
        "5. Rewrite hardcoded memory paths to the allowed root.\n"
        "----------------------------------------\n"
    )
    return head + (original or "")


def make_workflow(job, requester_email, slack_user_id, hook_url, hook_token):
    sid = hashlib.sha1(job["id"].encode("utf-8")).hexdigest()[:8]
    params = schedule_params(job)
    if not params:
        return None
    body = {
        "message": isolation_message(job.get("payload", {}).get("message", ""), slack_user_id, requester_email),
        "name": f"openclaw-sync:{job.get('name', 'job')}",
        "sessionKey": f"openclaw-sync:{slack_user_id}:{job['id']}",
        "wakeMode": job.get("wakeMode", "next-heartbeat"),
        "deliver": False,
    }
    return {
        "id": workflow_id(job["id"]),
        "name": f"OpenClaw Sync | {job.get('name','job')} | {requester_email or 'unknown'}",
        "nodes": [
            {
                "id": f"n1{sid}",
                "name": "Schedule Trigger",
                "type": "n8n-nodes-base.scheduleTrigger",
                "typeVersion": 1.2,
                "position": [240, 300],
                "parameters": params,
            },
            {
                "id": f"n2{sid}",
                "name": "Invoke OpenClaw Hook",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 4.2,
                "position": [560, 300],
                "parameters": {
                    "method": "POST",
                    "url": hook_url,
                    "sendHeaders": True,
                    "headerParameters": {"parameters": [{"name": "Authorization", "value": f"Bearer {hook_token}"}]},
                    "sendBody": True,
                    "specifyBody": "json",
                    "jsonBody": "=" + json.dumps(body, ensure_ascii=True),
                },
            },
        ],
        "connections": {"Schedule Trigger": {"main": [[{"node": "Invoke OpenClaw Hook", "type": "main", "index": 0}]]}},
        "settings": {"executionOrder": "v1"},
        "active": False,
        "pinData": {},
    }


def hash_item(job, hook_url, hook_token):
    base = json.dumps(job, sort_keys=True, ensure_ascii=True) + "|" + hook_url + "|" + hook_token + "|v1"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def sql_escape(v):
    return v.replace("'", "''")


def project_id_for_email(db_container, email):
    if not email:
        return None
    sql = (
        "SELECT p.id FROM project p JOIN \"user\" u ON u.id=p.\"creatorId\" "
        f"WHERE p.type='personal' AND lower(u.email)='{sql_escape(email.lower())}' LIMIT 1;"
    )
    out = run(["docker", "exec", "-i", db_container, "psql", "-U", "n8n", "-d", "n8n", "-At", "-c", sql]).strip()
    return out or None


def set_workflow_owners(db_container, assignments):
    if not assignments:
        return
    sqls = []
    for wid, pid in assignments.items():
        sqls.append(f"DELETE FROM shared_workflow WHERE \"workflowId\"='{sql_escape(wid)}';")
        sqls.append(
            "INSERT INTO shared_workflow (\"workflowId\",\"projectId\",role,\"createdAt\",\"updatedAt\") "
            f"VALUES ('{sql_escape(wid)}','{sql_escape(pid)}','workflow:owner',CURRENT_TIMESTAMP(3),CURRENT_TIMESTAMP(3));"
        )
    run(["docker", "exec", "-i", db_container, "psql", "-U", "n8n", "-d", "n8n", "-c", "\n".join(sqls)])


def set_active(db_container, state):
    if not state:
        return
    sqls = [f"UPDATE workflow_entity SET active={'true' if active else 'false'} WHERE id='{sql_escape(wid)}';" for wid, active in state.items()]
    run(["docker", "exec", "-i", db_container, "psql", "-U", "n8n", "-d", "n8n", "-c", "\n".join(sqls)])


def import_workflows(n8n_container, import_dir, files_dir):
    run(["docker", "exec", n8n_container, "sh", "-lc", f"rm -rf {import_dir}/* && mkdir -p {import_dir}"])
    run(["docker", "cp", f"{files_dir}/.", f"{n8n_container}:{import_dir}"])
    run(["docker", "exec", n8n_container, "n8n", "import:workflow", "--separate", "--input", import_dir])


def delete_workflows(db_container, workflow_ids):
    if not workflow_ids:
        return
    quoted = ",".join([f"'{sql_escape(x)}'" for x in workflow_ids])
    run(["docker", "exec", "-i", db_container, "psql", "-U", "n8n", "-d", "n8n", "-c", f"DELETE FROM workflow_entity WHERE id IN ({quoted});"])


def load_state(path):
    if not os.path.exists(path):
        return {"jobs": {}, "managed_workflow_ids": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=True, indent=2)
    os.replace(tmp, path)


def sync_once():
    state_file = os.environ.get("SYNC_STATE_FILE", "/state/state.json")
    session_glob = os.environ.get("OPENCLAW_SESSION_GLOB", "/home/openclaw/.openclaw/agents/main/sessions/*.jsonl")
    hook_url = os.environ["OPENCLAW_HOOK_URL"]
    hook_token = os.environ["OPENCLAW_HOOK_TOKEN"]
    n8n_container = os.environ.get("N8N_CONTAINER", "n8n-app")
    db_container = os.environ.get("N8N_DB_CONTAINER", "n8n-postgres")
    n8n_import_dir = os.environ.get("N8N_IMPORT_DIR", "/tmp/openclaw-sync")
    allowed_ids = csv_set_raw("SYNC_ALLOWED_SLACK_USER_IDS")
    allowed_emails = csv_set("SYNC_ALLOWED_EMAILS")
    require_slack_email = env_bool("SYNC_REQUIRE_SLACK_EMAIL_VERIFICATION", True)
    slack_bot_token = os.environ.get("SLACK_BOT_TOKEN", "")

    user_email_map = {}
    mapping_raw = os.environ.get("SYNC_USER_EMAIL_MAP", "")
    if mapping_raw:
        for item in mapping_raw.split(","):
            if "=" in item:
                k, v = item.split("=", 1)
                user_email_map[k.strip()] = v.strip().lower()

    jobs_payload = json.loads(run(["openclaw", "gateway", "call", "cron.list", "--json"]))
    jobs = jobs_payload.get("jobs", [])
    requesters = discover_requesters(session_glob)
    state = load_state(state_file)

    desired = {}
    skipped = []
    for job in jobs:
        job_id = job.get("id")
        if not job_id:
            continue
        req = requesters.get(job_id)
        if not req:
            skipped.append({"jobId": job_id, "reason": "no_requester_found"})
            continue
        sid = req.get("slack_user_id")
        if allowed_ids and sid not in allowed_ids:
            skipped.append({"jobId": job_id, "reason": "slack_user_not_allowed", "slackUserId": sid})
            continue
        verified_email = fetch_slack_email(slack_bot_token, sid)
        if require_slack_email and not verified_email:
            skipped.append({"jobId": job_id, "reason": "slack_email_unverified", "slackUserId": sid})
            continue
        email = (verified_email or user_email_map.get(sid) or req.get("email") or "").lower() or None
        if allowed_emails and email not in allowed_emails:
            skipped.append({"jobId": job_id, "reason": "email_not_allowed", "email": email})
            continue
        wf = make_workflow(job, email, sid, hook_url, hook_token)
        if not wf:
            skipped.append({"jobId": job_id, "reason": "unsupported_schedule"})
            continue
        desired[job_id] = {
            "workflow": wf,
            "requester": {"slack_user_id": sid, "email": email},
            "hash": hash_item(job, hook_url, hook_token),
            "enabled": bool(job.get("enabled", True)),
        }

    to_import = []
    next_jobs = {}
    for job_id, info in desired.items():
        prev = state.get("jobs", {}).get(job_id)
        if not prev or prev.get("hash") != info["hash"]:
            to_import.append(info["workflow"])
        next_jobs[job_id] = {
            "hash": info["hash"],
            "workflow_id": info["workflow"]["id"],
            "requester": info["requester"],
            "last_synced_at": int(time.time()),
        }

    prev_managed = set(state.get("managed_workflow_ids", []))
    cur_managed = {x["workflow"]["id"] for x in desired.values()}
    to_delete = sorted(list(prev_managed - cur_managed))

    if to_import:
        with tempfile.TemporaryDirectory() as td:
            for wf in to_import:
                with open(Path(td) / f"{wf['id']}.json", "w", encoding="utf-8") as f:
                    json.dump(wf, f, ensure_ascii=True, indent=2)
            import_workflows(n8n_container, n8n_import_dir, td)

    if to_delete:
        delete_workflows(db_container, to_delete)

    set_active(db_container, {info["workflow"]["id"]: info["enabled"] for info in desired.values()})

    owners = {}
    for info in desired.values():
        pid = project_id_for_email(db_container, info["requester"].get("email"))
        if pid:
            owners[info["workflow"]["id"]] = pid
    set_workflow_owners(db_container, owners)

    result = {"synced": len(to_import), "deleted": len(to_delete), "managed": len(cur_managed), "skipped": skipped}
    save_state(state_file, {
        "jobs": next_jobs,
        "managed_workflow_ids": sorted(list(cur_managed)),
        "last_run_at": int(time.time()),
        "skipped": skipped,
        "result": result,
    })
    return result


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, content_type, body_bytes):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def do_GET(self):
        if self.path == "/healthz":
            with LOCK:
                ok = bool(SYNC_STATUS.get("ok", False))
                payload = {
                    "ok": ok,
                    "last_run_at": SYNC_STATUS.get("last_run_at"),
                    "last_success_at": SYNC_STATUS.get("last_success_at"),
                    "last_error": SYNC_STATUS.get("last_error", ""),
                }
            self._send(200 if ok else 503, "application/json", json.dumps(payload, ensure_ascii=True).encode("utf-8"))
            return

        if self.path == "/metrics":
            with LOCK:
                result = SYNC_STATUS.get("last_result", {})
                ok_num = 1 if SYNC_STATUS.get("ok", False) else 0
                lines = [
                    "# HELP openclaw_sync_ok 1 if last run succeeded",
                    "# TYPE openclaw_sync_ok gauge",
                    f"openclaw_sync_ok {ok_num}",
                    "# HELP openclaw_sync_synced_last Number of workflows synced in last run",
                    "# TYPE openclaw_sync_synced_last gauge",
                    f"openclaw_sync_synced_last {int(result.get('synced', 0))}",
                    "# HELP openclaw_sync_deleted_last Number of workflows deleted in last run",
                    "# TYPE openclaw_sync_deleted_last gauge",
                    f"openclaw_sync_deleted_last {int(result.get('deleted', 0))}",
                    "# HELP openclaw_sync_managed_last Number of managed workflows in last run",
                    "# TYPE openclaw_sync_managed_last gauge",
                    f"openclaw_sync_managed_last {int(result.get('managed', 0))}",
                ]
            self._send(200, "text/plain; version=0.0.4", ("\n".join(lines) + "\n").encode("utf-8"))
            return

        self._send(404, "application/json", b'{"ok":false,"error":"not_found"}')

    def log_message(self, format, *args):
        return


def sync_loop():
    interval = int(os.environ.get("SYNC_INTERVAL_SECONDS", "60"))
    while True:
        now = int(time.time())
        try:
            result = sync_once()
            with LOCK:
                SYNC_STATUS["ok"] = True
                SYNC_STATUS["last_run_at"] = now
                SYNC_STATUS["last_success_at"] = now
                SYNC_STATUS["last_error"] = ""
                SYNC_STATUS["last_result"] = result
            print(json.dumps({"event": "sync_ok", **result}, ensure_ascii=True), flush=True)
        except Exception as e:
            with LOCK:
                SYNC_STATUS["ok"] = False
                SYNC_STATUS["last_run_at"] = now
                SYNC_STATUS["last_error"] = str(e)
            print(json.dumps({"event": "sync_error", "error": str(e)}, ensure_ascii=True), flush=True)
        time.sleep(max(5, interval))


def main():
    port = int(os.environ.get("SYNC_METRICS_PORT", "18090"))
    thread = threading.Thread(target=sync_loop, daemon=True)
    thread.start()
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(json.dumps({"event": "metrics_server_started", "port": port}, ensure_ascii=True), flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
