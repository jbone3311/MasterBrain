"""Fictional-data browser trial using the real PostgreSQL store and Brain API.

Run with --synthetic-preview. Creates its own temporary Docker PostgreSQL; accepts
no account, filesystem root, credential or database configuration from the user.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from starlette.middleware.trustedhost import TrustedHostMiddleware

from email_brain.api import create_app
from email_brain.auth import Credential, TokenRegistry
from email_brain.domain.models import TenantContext
from email_brain.migrate import grant_runtime, migrate
from email_brain.schemas import SearchRequest
from email_brain.store import IngestItem, Store
from masterbrain.datacore.extraction import FileOSAdapter
from masterbrain.datacore.fileos import snapshot_tree
from masterbrain.datacore.persistence import DataCoreStore

ROOT = Path(__file__).resolve().parents[1]
ASSETS = Path(__file__).with_name("cross_source_assets")
REVISION = "synthetic-cross-source-v1"
READ_SCOPES = frozenset({
    "brain.search", "brain.evidence.read", "brain.content.read",
    "brain.changes.read", "knowledge.search",
})
WRITE_SCOPES = frozenset({
    "email.ingest", "email.search", "email.evidence.read",
    "brain.source.ingest", "brain.document.publish", "brain.index.activate",
})
FILES = {
    "cedar-term-sheet.txt": (
        "Cedar Harbor fictional loan term sheet. Proposed loan amount: $8,000,000. "
        "Required debt service coverage ratio: 1.25. This is synthetic test evidence."
    ),
    "cedar-checklist.txt": (
        "Cedar Harbor closing checklist. Insurance certificate remains outstanding. "
        "The appraisal has been received. Target closing is October 15, 2026."
    ),
    "juniper-note.txt": "Juniper Plaza unrelated fictional project. Budget review is complete.",
}
MAIL = [
    ("Cedar Harbor appraisal", "Cedar Harbor appraisal received. Please review the valuation."),
    ("Cedar Harbor insurance", "Cedar Harbor insurance certificate is still outstanding."),
    ("Juniper Plaza update", "Juniper Plaza budget review is complete."),
]


@dataclass
class Preview:
    app: FastAPI
    token: str
    other_token: str
    context: TenantContext
    other_context: TenantContext
    file_hashes: dict[str, str]


def new_tenant(admin: str) -> tuple[TenantContext, UUID]:
    tenant, actor, account = uuid4(), uuid4(), uuid4()
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO tenants(id,name) VALUES (%s,'Fictional browser trial')", (tenant,)
        )
        conn.execute(
            "INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES (%s,%s,'owner')",
            (tenant, actor),
        )
        conn.execute(
            "INSERT INTO mail_accounts(id,tenant_id,provider,address,secret_ref) "
            "VALUES (%s,%s,'fastmail','trial@example.invalid','synthetic:none')",
            (account, tenant),
        )
    return TenantContext(tenant, actor, READ_SCOPES | WRITE_SCOPES, uuid4()), account


def publish_files(store: Store, ctx: TenantContext, root: Path, files: dict[str, str]) -> None:
    root.mkdir()
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    core = DataCoreStore(store)
    manifest = snapshot_tree(
        root, source_id="trial_files", observed_at=datetime(2026, 9, 24, tzinfo=UTC)
    )
    key = uuid4()
    published = FileOSAdapter(core).publish_snapshot(
        ctx, root, manifest, key, code_revision=REVISION
    )
    assert published.counts == {"extracted": len(files)}
    ids = {item["version_id"]: item["item_id"] for item in manifest["items"]}
    receipt = core.complete_fileos_run(
        ctx, manifest, key, outcomes=published.counts,
        item_outcomes={
            ids[p.extraction.version_id]: p.extraction.status.value for p in published.results
        },
        published_documents=len(files), code_revision=REVISION, document_processor_version=None,
    )
    generation = core.build_fileos_index_generation(
        ctx, "trial_files", receipt.run_id, code_revision=REVISION
    )
    core.activate_fileos_index_generation(ctx, "trial_files", generation.generation_id, uuid4())


def credential(ctx: TenantContext, token: str, scopes: frozenset[str] = READ_SCOPES) -> Credential:
    return Credential(
        token_sha256=hashlib.sha256(token.encode()).hexdigest(),
        tenant_id=ctx.tenant_id, actor_id=ctx.actor_id, scopes=set(scopes),
        expires_at=datetime.now(UTC) + timedelta(hours=2), client_kind="human",
    )


def build_preview(store: Store, admin: str, temporary_root: Path) -> Preview:
    """Test-harness setup only. All source paths are newly created fictional fixtures."""
    admin_config = conninfo_to_dict(admin)
    runtime_config = conninfo_to_dict(store.dsn)
    if (
        not admin_config.get("dbname", "").startswith("email_brain_test")
        or admin_config.get("host") not in {"127.0.0.1", "localhost", "::1"}
        or any(
            admin_config.get(key) != runtime_config.get(key) for key in ("host", "port", "dbname")
        )
    ):
        raise ValueError("Only matching disposable loopback test databases are allowed")
    ctx, account = new_tenant(admin)
    other, _ = new_tenant(admin)
    observed = datetime(2026, 9, 24, tzinfo=UTC)
    messages = [
        IngestItem(
            f"trial-event-{n}", f"trial-message-{n}", f"trial-version-{n}", observed,
            (f"From: alex@example.invalid\r\nTo: owner@example.invalid\r\n"
             f"Subject: {subject}\r\n\r\n{body}").encode(),
        )
        for n, (subject, body) in enumerate(MAIL)
    ]
    assert store.ingest_page(ctx, account, None, "trial-page-1", messages) == len(MAIL)
    core = DataCoreStore(store)
    for query in ("Cedar Harbor", "Juniper Plaza"):
        for hit in store.search(ctx, SearchRequest(query=query)):
            core.bridge_current_email_version(
                ctx, hit["evidence_id"], uuid4(), code_revision=REVISION
            )
    publish_files(store, ctx, temporary_root / "owner", FILES)
    publish_files(store, other, temporary_root / "other", {
        "other-private.txt": "Cedar Harbor other-tenant-canary must not appear for the first user."
    })
    token, other_token = secrets.token_urlsafe(40), secrets.token_urlsafe(40)
    registry = TokenRegistry([credential(ctx, token), credential(other, other_token)])
    app = create_app(store, registry)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    @app.get("/trial", include_in_schema=False)
    def trial() -> FileResponse:
        return FileResponse(ASSETS / "index.html", media_type="text/html")

    @app.get("/trial.js", include_in_schema=False)
    def javascript() -> FileResponse:
        return FileResponse(ASSETS / "trial.js", media_type="application/javascript")

    @app.get("/trial.css", include_in_schema=False)
    def stylesheet() -> FileResponse:
        return FileResponse(ASSETS / "trial.css", media_type="text/css")

    hashes = {name: hashlib.sha256(text.encode()).hexdigest() for name, text in FILES.items()}
    return Preview(app, token, other_token, replace(ctx, scopes=READ_SCOPES),
                   replace(other, scopes=READ_SCOPES), hashes)


def docker(*args: str, env: dict[str, str] | None = None) -> str:
    return subprocess.check_output(
        ["docker", *args], env=env, text=True, stderr=subprocess.PIPE, timeout=180,
    ).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-preview", action="store_true", required=True)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be 1024..65535")
    if not shutil.which("docker"):
        parser.error("Docker Desktop must be installed and running for this disposable trial")
    name = "masterbrain-trial-" + secrets.token_hex(6)
    password = secrets.token_urlsafe(32)
    container_id: str | None = None
    stage = "starting disposable PostgreSQL"
    try:
        print("Creating fictional-data trial. No live accounts or source folders are used.")
        container_id = docker(
            "run", "--detach", "--rm", "--name", name,
            "--publish", "127.0.0.1::5432", "--tmpfs", "/var/lib/postgresql/data",
            "--env", "POSTGRES_PASSWORD", "--env", "POSTGRES_DB=email_brain_test_preview",
            "postgres:17", env={**os.environ, "POSTGRES_PASSWORD": password},
        )
        port = docker("port", name, "5432/tcp").split(":")[-1]
        admin = make_conninfo(
            host="127.0.0.1", port=port, dbname="email_brain_test_preview",
            user="postgres", password=password, connect_timeout=2,
        )
        for attempt in range(60):
            try:
                with psycopg.connect(admin):
                    break
            except psycopg.OperationalError:
                if attempt == 59:
                    raise
                time.sleep(1)
        stage = "initializing synthetic schema"
        migrate(admin, ROOT / "migrations")
        runtime_password = secrets.token_urlsafe(32)
        with psycopg.connect(admin) as conn:
            conn.execute(
                sql.SQL("CREATE ROLE trial_runtime LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD {}")
                .format(sql.Literal(runtime_password))
            )
            grant_runtime(conn, "trial_runtime")
        runtime = make_conninfo(admin, user="trial_runtime", password=runtime_password)
        stage = "seeding and validating fictional evidence"
        with tempfile.TemporaryDirectory(prefix="masterbrain-fictional-") as folder:
            preview = build_preview(Store(runtime), admin, Path(folder))
            url = f"http://127.0.0.1:{args.port}/trial#{preview.token}"
            listener = socket.create_server(("127.0.0.1", args.port))
            opener = threading.Timer(1.5, webbrowser.open, args=(url,))
            opener.daemon = True
            opener.start()
            print(f"Trial opening at http://127.0.0.1:{args.port}/trial . Stop with Ctrl-C.")
            print("Two-hour read-only trial credential stays in browser memory.")
            print("No real token is needed. Restart the launcher if the tab loses its credential.")
            stage = "serving the loopback browser trial"
            try:
                config = uvicorn.Config(
                    preview.app, host="127.0.0.1", port=args.port, access_log=False
                )
                uvicorn.Server(config).run(sockets=[listener])
            finally:
                opener.cancel()
                listener.close()
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(
            f"Trial stopped while {stage} ({type(exc).__name__}); details suppressed.",
            file=sys.stderr,
        )
        return 1
    finally:
        if container_id is not None:
            try:
                docker("rm", "--force", container_id)
            except (subprocess.SubprocessError, OSError):
                print(
                    f"Check Docker Desktop for temporary trial container {name}.", file=sys.stderr
                )


if __name__ == "__main__":
    raise SystemExit(main())
