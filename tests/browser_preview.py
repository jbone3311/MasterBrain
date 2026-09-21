"""Opt-in loopback synthetic UI fixture; not a database/worker acceptance test.

Run: .venv/bin/python tests/browser_preview.py --synthetic-preview
Owner token: synthetic-preview-only (not a real credential).
No real files beyond the UI assets, mailboxes, models, database or Docker are read.
"""

import argparse
import json
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from uuid import uuid4

ACCOUNT = "00000000-0000-4000-8000-000000000001"
RECEIPT = "00000000-0000-4000-8000-000000000101"
PARSER = "sandbox-mime-v1-" + "a" * 64
ROOT = Path(__file__).resolve().parents[1] / "src/email_brain/web"
TOKEN = "synthetic-preview-only"


class Preview(BaseHTTPRequestHandler):
    jobs: list[dict[str, object]] = []
    keys: dict[str, dict[str, object]] = {}

    def log_message(self, format, *args):
        pass  # No paths, auth headers or input bodies in access logs.

    def send_json(self, payload, status=200):
        raw = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def authorized(self):
        if self.headers.get("Authorization") != f"Bearer {TOKEN}":
            self.send_json({"error": "synthetic_preview_token_required"}, 401)
            return False
        return True

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        assets = {
            "/": ("index.html", "text/html"),
            "/app.js": ("app.js", "text/javascript"),
            "/style.css": ("style.css", "text/css"),
        }
        if path in assets:
            name, media = assets[path]
            raw = (ROOT / name).read_bytes()
            if name == "index.html":
                raw = raw.replace(
                    b"<body><main>",
                    b"<body><main><p>SYNTHETIC UI PREVIEW: simulated jobs, "
                    b"no database or mailbox.</p>",
                )
            self.send_response(200)
            self.send_header("Content-Type", media)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)
            return
        if not self.authorized():
            return
        prefix = f"/v1/accounts/{ACCOUNT}"
        if path == "/readyz":
            self.send_json({"status": "ready"})
        elif path == prefix + "/sync-status":
            self.send_json(
                {"message_counts": {"ready": 0, "quarantined": 1, "deleted": 0}, "worker": None}
            )
        elif path == prefix + "/quarantine":
            self.send_json(
                {
                    "results": [
                        {
                            "id": RECEIPT,
                            "reason": "mime_too_large",
                            "provider_id": "synthetic-held-message",
                            "parser_version": "stdlib-mime-v4",
                            "raw_sha256": "b" * 64,
                            "received_at": datetime.now(UTC).isoformat(),
                        }
                    ],
                    "next_after": None,
                    "raw_access": False,
                    "reprocessing": True,
                    "retry_parser_version": "stdlib-mime-v4",
                }
            )
        elif path == prefix + "/processing":
            self.send_json(
                {
                    "enabled": True,
                    "parser_version": PARSER,
                    "worker_online": None,
                    "mailbox_effects": False,
                }
            )
        elif path == prefix + "/processing/jobs":
            self.send_json(
                {
                    "results": self.jobs[:50],
                    "next_after": None,
                    "limit": 50,
                    "mailbox_effects": False,
                }
            )
        elif path.startswith(prefix + "/processing/"):
            match = next((job for job in self.jobs if path.endswith("/" + str(job["id"]))), None)
            self.send_json(match or {"error": "not_found"}, 200 if match else 404)
        else:
            self.send_json({"error": "not_found"}, 404)

    def do_POST(self):
        if not self.authorized():
            return
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 <= length <= 32768:
            self.send_json({"error": "request_too_large"}, 413)
            return
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            self.send_json({"error": "invalid_request"}, 422)
            return
        prefix = f"/v1/accounts/{ACCOUNT}"
        if self.path == prefix + f"/quarantine/{RECEIPT}/jobs":
            key = self.headers.get("Idempotency-Key")
            if body != {"expected_parser_version": PARSER} or not key:
                self.send_json({"error": "invalid_request"}, 422)
                return
            if key not in self.keys:
                now = datetime.now(UTC)
                job = {
                    "id": str(uuid4()),
                    "account_id": ACCOUNT,
                    "receipt_id": RECEIPT,
                    "parser_version": PARSER,
                    "status": "queued",
                    "attempts": 0,
                    "created_at": now.isoformat(),
                    "expires_at": (now + timedelta(hours=1)).isoformat(),
                    "retry_at": None,
                    "completed_at": None,
                    "attempt_id": None,
                    "outcome": None,
                    "mailbox_effects": False,
                }
                self.keys[key] = job
                self.jobs.insert(0, job)
            self.send_json(self.keys[key], 202)
        elif self.path.startswith(prefix + "/processing/") and self.path.endswith("/cancel"):
            job_id = self.path.rsplit("/", 2)[1]
            match = next((job for job in self.jobs if job["id"] == job_id), None)
            if match:
                match.update(
                    status="cancelled",
                    outcome="cancelled",
                    completed_at=datetime.now(UTC).isoformat(),
                )
            self.send_json(match or {"error": "not_found"}, 200 if match else 404)
        else:
            self.send_json({"error": "preview_operation_disabled"}, 409)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-preview", action="store_true", required=True)
    args = parser.parse_args()
    server = HTTPServer(("127.0.0.1", 0), Preview)
    print(f"Synthetic preview only: http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
