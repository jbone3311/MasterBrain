"""Local prototype commands. No live provider or model credentials are used by the demo."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import uvicorn
from psycopg import sql

from email_brain.api import create_app
from email_brain.auth import SCOPES, TokenRegistry
from email_brain.domain.models import TenantContext
from email_brain.migrate import grant_runtime, migrate
from email_brain.store import IngestItem, Store
from email_brain.synthetic import fake_email


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"{name} must be set")
    return value


def _private_file(path: Path, value: str) -> None:
    # Exclusive create: never overwrite an existing credential or follow a symlink.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as output:
        output.write(value)


def provision_demo(state: Path) -> None:
    if not state.is_absolute() or "Dropbox" in state.parts:
        raise ValueError("state must use an absolute path outside Dropbox")
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    if (state / "credentials.json").exists() or (state / "owner-token.txt").exists():
        raise ValueError("demo credentials already exist; choose a new state directory")
    password = _env("EMAIL_BRAIN_RUNTIME_PASSWORD")
    if len(password) < 24:
        raise ValueError("runtime password must have at least 24 characters")
    tenant_id, actor_id, account_id = uuid4(), uuid4(), uuid4()
    with psycopg.connect(_env("EMAIL_BRAIN_ADMIN_DSN")) as conn:
        # Fail if the role exists: never rotate/alter an unrelated installation silently.
        conn.execute(
            sql.SQL(
                "CREATE ROLE email_brain_runtime LOGIN NOSUPERUSER NOBYPASSRLS "
                "NOCREATEDB NOCREATEROLE NOINHERIT PASSWORD {}"
            ).format(sql.Literal(password))
        )
        grant_runtime(conn, "email_brain_runtime")
        conn.execute("INSERT INTO tenants(id,name) VALUES (%s,'Synthetic demo')", (tenant_id,))
        conn.execute(
            "INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES (%s,%s,'owner')",
            (tenant_id, actor_id),
        )
        conn.execute(
            "INSERT INTO mail_accounts(id,tenant_id,provider,address,secret_ref) "
            "VALUES (%s,%s,'fastmail','owner@example.invalid','synthetic:no-token')",
            (account_id, tenant_id),
        )
    token = secrets.token_urlsafe(40)
    credential = [
        {
            "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
            "tenant_id": str(tenant_id),
            "actor_id": str(actor_id),
            "scopes": sorted(SCOPES - {"email.ingest"}),
            "client_kind": "human",
            "expires_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
        }
    ]
    _private_file(state / "credentials.json", json.dumps(credential, indent=2))
    _private_file(state / "owner-token.txt", token)
    _private_file(
        state / "demo.json",
        json.dumps(
            {"tenant_id": str(tenant_id), "actor_id": str(actor_id), "account_id": str(account_id)}
        ),
    )
    print(f"Synthetic owner created. Credentials are private files in {state}; token not logged.")


def seed(state: Path) -> None:
    data = json.loads((state / "demo.json").read_text())
    ctx = TenantContext(
        UUID(data["tenant_id"]), UUID(data["actor_id"]), frozenset({"email.ingest"}), uuid4()
    )
    contents = (
        (
            "Melron investment update",
            "The Melron project briefing is ready. Please reply by Friday.",
        ),
        (
            "Synthetic receipt",
            "Your example subscription receipt is attached in this fictional message.",
        ),
        (
            "Project introduction",
            "Meet Alex from Melron. We would like to schedule a project review.",
        ),
    )
    items = [
        IngestItem(
            event_key=f"demo-{index}",
            provider_id=f"synthetic-{index}",
            version="demo-v1",
            received_at=datetime(2026, 9, 19, 12, index, tzinfo=UTC),
            raw=(
                f"From: Alex <alex@example.invalid>\r\nTo: owner@example.invalid\r\n"
                f"Subject: {subject}\r\nMessage-ID: <synthetic-{index}@example.invalid>\r\n"
                f"Content-Type: text/plain; charset=utf-8\r\n\r\n{body}\r\n"
            ).encode(),
        )
        for index, (subject, body) in enumerate(contents)
    ]
    count = Store(_env("EMAIL_BRAIN_DSN")).ingest_page(
        ctx, UUID(data["account_id"]), None, "synthetic-complete-v1", items
    )
    print(f"Synthetic page committed: {count} new events (replays are no-ops).")


def seed_corpus(state: Path, count: int) -> None:
    """Resumable synthetic-only backfill for a fresh demo; refuse unrelated cursors."""
    if type(count) is not int or not 1 <= count <= 10000:
        raise ValueError("synthetic corpus count must be 1..10000")
    data = json.loads((state / "demo.json").read_text())
    ctx = TenantContext(
        UUID(data["tenant_id"]), UUID(data["actor_id"]), frozenset({"email.ingest"}), uuid4()
    )
    account = UUID(data["account_id"])
    store = Store(_env("EMAIL_BRAIN_DSN"))
    with store.transaction(ctx) as conn:
        row = conn.execute(
            "SELECT opaque_cursor FROM sync_cursors WHERE account_id=%s AND scope='email'",
            (account,),
        ).fetchone()
    prefix = f"synthetic-corpus-v1:{count}:"
    cursor = row["opaque_cursor"] if row else None
    if cursor is not None and not cursor.startswith(prefix):
        raise ValueError("fresh synthetic account or matching corpus required")
    position = int(cursor[len(prefix) :]) if cursor else 0
    if not 0 <= position <= count:
        raise ValueError("invalid synthetic checkpoint")
    while position < count:
        stop = min(position + 100, count)
        items = [
            IngestItem(
                f"corpus-v1-{index}",
                f"synthetic-corpus-{index}",
                "corpus-v1",
                datetime(2026, 9, 19, 12, tzinfo=UTC),
                fake_email(index),
            )
            for index in range(position, stop)
        ]
        next_cursor = f"{prefix}{stop}"
        store.ingest_page(ctx, account, cursor, next_cursor, items)
        position, cursor = stop, next_cursor
    print(f"Synthetic corpus ready: {count} fictional messages; no provider or model contacted.")


def main() -> None:
    parser = argparse.ArgumentParser(prog="email-brain")
    commands = parser.add_subparsers(dest="command", required=True)
    migration = commands.add_parser("migrate", help="Administrator-only schema migration")
    migration.add_argument("--directory", type=Path, default=Path("migrations"))
    for command in ("init-demo", "seed-demo"):
        commands.add_parser(command).add_argument("--state-dir", type=Path, required=True)
    corpus = commands.add_parser("seed-corpus", help="Import fictional emails, no provider calls")
    corpus.add_argument("--state-dir", type=Path, required=True)
    corpus.add_argument("--count", type=int, default=256)
    serve = commands.add_parser("serve", help="Loopback-only developer server")
    serve.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    try:
        if args.command == "migrate":
            print("Applied:", migrate(_env("EMAIL_BRAIN_ADMIN_DSN"), args.directory))
        elif args.command == "init-demo":
            provision_demo(args.state_dir)
        elif args.command == "seed-demo":
            seed(args.state_dir)
        elif args.command == "seed-corpus":
            seed_corpus(args.state_dir, args.count)
        else:
            app = create_app(
                Store(_env("EMAIL_BRAIN_DSN")),
                TokenRegistry.from_file(Path(_env("EMAIL_BRAIN_CREDENTIALS_FILE"))),
            )
            uvicorn.run(
                app, host="127.0.0.1", port=args.port, access_log=False, proxy_headers=False
            )
    except (ValueError, OSError, psycopg.Error):
        # Do not echo exception contents: a DSN or SQL error can contain credentials.
        parser.exit(
            1,
            "Operation failed. Check configuration, permissions and service availability. "
            "Sensitive exception details suppressed.\n",
        )


if __name__ == "__main__":
    main()
