"""Fictional-data browser trial using the real PostgreSQL store and Brain API.

Run with --synthetic-preview. Creates its own disposable PostgreSQL 17 cluster;
accepts no account, filesystem root, credential or database configuration.
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
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.testclient import TestClient
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
from masterbrain.knowledge import KnowledgeCore
from masterbrain.knowledge_schema import CommitmentWrite
from masterbrain.statement_persistence import StatementProposalStore

ROOT = Path(__file__).resolve().parents[1]
ASSETS = Path(__file__).with_name("cross_source_assets")
REVISION = "synthetic-cross-source-v1"
READ_SCOPES = frozenset({
    "brain.search", "brain.evidence.read", "brain.content.read",
    "brain.changes.read", "knowledge.search", "knowledge.read",
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
    "maple-closing-memo.txt": (
        "Maple Arcade closing target is November 12, 2026. "
        "This fictional memo has not been reconciled with email correspondence."
    ),
    "cobalt-statement.txt": (
        "Account No: 000000\nPeriod: April - 2024\nLong $100.00\n"
        "Symbol Description Quantity Market Price Market Value Cost Price "
        "Unrealized TD Cost Basis\n"
        "ACME Fictional Corporation 2 $50.00 $100.00 $40.00 $20.00 $80.00"
    ),
}
MAIL = [
    ("Cedar Harbor appraisal", "Cedar Harbor appraisal received. Please review the valuation."),
    ("Cedar Harbor insurance", "Cedar Harbor insurance certificate is still outstanding."),
    ("Juniper Plaza update", "Juniper Plaza budget review is complete."),
    ("Maple Arcade closing", "Maple Arcade closing target is November 19, 2026."),
]


@dataclass
class Preview:
    app: FastAPI
    token: str
    other_token: str
    context: TenantContext
    other_context: TenantContext
    file_hashes: dict[str, str]
    statement_proposal_id: str


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


def publish_files(
    store: Store, ctx: TenantContext, root: Path, files: dict[str, str]
) -> dict[str, str]:
    root.mkdir()
    # Match the private controller: canonicalize our newly created synthetic root.
    root = root.resolve(strict=True)
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
    if published.counts != {"extracted": len(files)}:
        raise RuntimeError("Synthetic file publication did not complete")
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
    return {
        result.extraction.locator: result.publication.document_id
        for result in published.results if result.publication is not None
    }


def publish_reviewed_knowledge(store: Store, ctx: TenantContext) -> None:
    """One fictional, human-reviewed cross-source interpretation for Ask."""
    core = DataCoreStore(store)
    email = core.search_current_email_family(ctx, "insurance", message_limit=1).messages
    files = core.search_current_fileos(ctx, "insurance", limit=1)
    if len(email) != 1 or len(files) != 1:
        raise RuntimeError("Synthetic knowledge evidence is incomplete")
    reviewer = replace(ctx, scopes=ctx.scopes | frozenset({"knowledge.review"}))
    KnowledgeCore(store).publish(
        reviewer,
        CommitmentWrite(
            kind="commitment",
            description="Closing readiness follow-up: obtain outstanding certificate",
            state="open",
            evidence_ids=[email[0].evidence_id, files[0].evidence_id],
            source_quote="Insurance certificate remains outstanding.",
            confidence=0.9,
            observed_at=datetime(2026, 9, 24, tzinfo=UTC),
            reviewed=True,
        ),
        uuid4(),
    )


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
    count = store.ingest_page(ctx, account, None, "trial-page-1", messages)
    if count != len(MAIL):
        raise RuntimeError("Synthetic email ingestion did not complete")
    core = DataCoreStore(store)
    for query in ("Cedar Harbor", "Juniper Plaza", "Maple Arcade"):
        for hit in store.search(ctx, SearchRequest(query=query)):
            core.bridge_current_email_version(
                ctx, hit["evidence_id"], uuid4(), code_revision=REVISION
            )
    file_documents = publish_files(store, ctx, temporary_root / "owner", FILES)
    statement = StatementProposalStore(store).project_current_document(
        ctx, file_documents["cobalt-statement.txt"], uuid4()
    )
    if statement["row_count"] != 1 or statement["status"] != "reconciled":
        raise RuntimeError("Fictional statement proposal did not reconcile")
    publish_reviewed_knowledge(store, ctx)
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

    @app.get("/trial/statement-id", include_in_schema=False)
    def statement_id(request: Request) -> JSONResponse:
        # The random locator is disclosed only to the owner trial credential.
        if not secrets.compare_digest(request.headers.get("authorization", ""), f"Bearer {token}"):
            raise HTTPException(status_code=404)
        return JSONResponse(
            {"proposal_id": statement["proposal_id"]}, headers={"Cache-Control": "no-store"}
        )

    @app.get("/trial.js", include_in_schema=False)
    def javascript() -> FileResponse:
        return FileResponse(ASSETS / "trial.js", media_type="application/javascript")

    @app.get("/trial.css", include_in_schema=False)
    def stylesheet() -> FileResponse:
        return FileResponse(ASSETS / "trial.css", media_type="text/css")

    hashes = {name: hashlib.sha256(text.encode()).hexdigest() for name, text in FILES.items()}
    return Preview(app, token, other_token, replace(ctx, scopes=READ_SCOPES),
                   replace(other, scopes=READ_SCOPES), hashes, statement["proposal_id"])


def docker(*args: str, env: dict[str, str] | None = None) -> str:
    return subprocess.check_output(
        ["docker", *args], env=env, text=True, stderr=subprocess.PIPE, timeout=180,
    ).strip()


def cleanup_trial_container(name: str, marker: str) -> None:
    """Remove only the container with this run's unpredictable name and marker."""
    try:
        inspected = docker(
            "inspect", "--format", '{{ index .Config.Labels "masterbrain.trial" }} {{.Id}}',
            name,
        )
        found_marker, separator, container_id = inspected.partition(" ")
        if found_marker != marker or not separator or not container_id:
            raise ValueError("trial container identity mismatch")
        docker("rm", "--force", container_id)
    except (subprocess.SubprocessError, OSError, ValueError):
        print(
            f"Check Docker Desktop for temporary trial container {name}.", file=sys.stderr
        )


@contextmanager
def docker_database() -> Iterator[str]:
    name = "masterbrain-trial-" + secrets.token_hex(6)
    password = secrets.token_urlsafe(32)
    marker = secrets.token_hex(16)
    try:
        docker(
            "run", "--detach", "--rm", "--name", name,
            "--label", f"masterbrain.trial={marker}",
            "--publish", "127.0.0.1::5432", "--tmpfs", "/var/lib/postgresql/data",
            "--env", "POSTGRES_PASSWORD", "--env", "POSTGRES_DB=email_brain_test_preview",
            "postgres:17", env={**os.environ, "POSTGRES_PASSWORD": password},
        )
        port = docker("port", name, "5432/tcp").split(":")[-1]
        admin = make_conninfo(
            host="127.0.0.1", port=port, dbname="email_brain_test_preview",
            user="postgres", password=password, connect_timeout=2,
        )
        yield admin
    finally:
        cleanup_trial_container(name, marker)


def local_postgres_binaries() -> tuple[Path, Path] | None:
    found = shutil.which("initdb")
    if not found:
        return None
    initdb = Path(found).resolve()
    pg_ctl = initdb.parent / "pg_ctl"
    if not pg_ctl.is_file() or not os.access(pg_ctl, os.X_OK):
        return None
    for binary, expected in (
        (initdb, "initdb (PostgreSQL) 17."),
        (pg_ctl, "pg_ctl (PostgreSQL) 17."),
    ):
        try:
            version = subprocess.check_output(
                [str(binary), "--version"], text=True, stderr=subprocess.DEVNULL,
                timeout=5,
            )
        except (subprocess.SubprocessError, OSError):
            return None
        if not version.startswith(expected):
            return None
    return initdb, pg_ctl


def free_loopback_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


@contextmanager
def local_database() -> Iterator[str]:
    binaries = local_postgres_binaries()
    if binaries is None:
        raise RuntimeError("Local PostgreSQL 17 initdb and pg_ctl are required")
    initdb, pg_ctl = binaries
    root = Path(tempfile.mkdtemp(prefix="masterbrain-trial-pg-"))
    data = root / "data"
    password_file = root / "password"
    password = secrets.token_urlsafe(32)
    port = free_loopback_port()
    pg_env = {key: value for key, value in os.environ.items() if not key.startswith("PG")}
    try:
        password_file.write_text(password + "\n", encoding="utf-8")
        password_file.chmod(0o600)
        try:
            subprocess.run(
                [str(initdb), "-D", str(data), "--username=trial_admin",
                 "--auth-host=scram-sha-256", "--auth-local=reject",
                 f"--pwfile={password_file}"],
                env=pg_env, capture_output=True, text=True, timeout=90, check=True,
            )
        finally:
            password_file.unlink(missing_ok=True)
        subprocess.run(
            [str(pg_ctl), "-D", str(data), "-l", str(root / "postgres.log"),
             "-o", f"-h 127.0.0.1 -p {port} -c unix_socket_directories=''",
             "-w", "-t", "30", "start"],
            env=pg_env, capture_output=True, text=True, timeout=45, check=True,
        )
        bootstrap = make_conninfo(
            host="127.0.0.1", port=port, dbname="postgres", user="trial_admin",
            password=password, connect_timeout=2,
        )
        with psycopg.connect(bootstrap, autocommit=True) as conn:
            conn.execute("CREATE DATABASE email_brain_test_preview")
        yield make_conninfo(bootstrap, dbname="email_brain_test_preview")
    finally:
        # A startup timeout may still have launched PostgreSQL. Never remove a
        # possibly running cluster; keep its exact private path for inspection.
        if (data / "postmaster.pid").exists():
            try:
                stopped = subprocess.run(
                    [str(pg_ctl), "-D", str(data), "-m", "fast", "-w", "-t", "30", "stop"],
                    env=pg_env, capture_output=True, text=True, timeout=45, check=False,
                ).returncode == 0
            except (subprocess.SubprocessError, OSError):
                stopped = False
            if not stopped:
                print(f"Check temporary synthetic PostgreSQL cluster at {root}.",
                      file=sys.stderr)
                raise RuntimeError("Temporary synthetic PostgreSQL stop was not confirmed")
        shutil.rmtree(root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-preview", action="store_true", required=True)
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--backend", choices=("auto", "docker", "local"), default="auto")
    parser.add_argument(
        "--self-test", action="store_true", help="validate then clean up without a browser"
    )
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be 1024..65535")
    backend = args.backend
    if backend == "auto":
        backend = "docker" if shutil.which("docker") else "local"
    if backend == "docker" and not shutil.which("docker"):
        parser.error("Docker Desktop is unavailable; use --backend local with PostgreSQL 17")
    if backend == "local" and local_postgres_binaries() is None:
        parser.error("PostgreSQL 17 initdb and pg_ctl are required for --backend local")
    stage = "running fictional trial"
    try:
        print("Creating fictional-data trial. No live accounts or source folders are used.")
        database = docker_database() if backend == "docker" else local_database()
        with database as admin:
            for attempt in range(60):
                try:
                    with psycopg.connect(admin):
                        break
                except psycopg.OperationalError:
                    if attempt == 59:
                        raise
                    time.sleep(1)
            return serve_trial(admin, args.port, args.self_test)
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(
            f"Trial stopped while {stage} ({type(exc).__name__}); details suppressed.",
            file=sys.stderr,
        )
        return 1


def serve_trial(admin: str, port: int, self_test: bool) -> int:
    migrate(admin, ROOT / "migrations")
    try:
        runtime_password = secrets.token_urlsafe(32)
        with psycopg.connect(admin) as conn:
            conn.execute(
                sql.SQL("CREATE ROLE trial_runtime LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD {}")
                .format(sql.Literal(runtime_password))
            )
            grant_runtime(conn, "trial_runtime")
        runtime = make_conninfo(admin, user="trial_runtime", password=runtime_password)
        with tempfile.TemporaryDirectory(prefix="masterbrain-fictional-") as folder:
            preview = build_preview(Store(runtime), admin, Path(folder))
            if self_test:
                with TestClient(
                    preview.app, base_url="http://127.0.0.1",
                    headers={"Authorization": "Bearer " + preview.token},
                ) as client:
                    response = client.post(
                        "/v1/brain/current-search", json={"query": "Cedar Harbor"}
                    )
                    data = response.json()
                    if response.status_code != 200 or any(
                        len(data["layers"][key]) != 2 for key in ("email_messages", "fileos")
                    ):
                        raise RuntimeError("Synthetic startup search failed")
                    for key in ("email_messages", "fileos"):
                        evidence_id = data["layers"][key][0]["evidence_id"]
                        content = client.post(
                            f"/v1/brain/evidence/{evidence_id}/content", json={"max_chars": 4000}
                        )
                        if content.status_code != 200:
                            raise RuntimeError("Synthetic startup citation failed")
                    if client.get("/v1/brain/current-coverage").status_code != 200:
                        raise RuntimeError("Synthetic startup coverage failed")
                    knowledge_answer = client.post(
                        "/v1/brain/answers", json={"question": "readiness"}
                    )
                    if (
                        knowledge_answer.status_code != 200
                        or knowledge_answer.json().get("status") != "no_supported_answer"
                        or knowledge_answer.json().get("citations") != []
                        or len(knowledge_answer.json().get("reviewed_knowledge", [])) != 1
                    ):
                        raise RuntimeError("Synthetic startup knowledge Ask failed")
                    insurance = client.post(
                        "/v1/brain/answers",
                        json={"question": "Find the insurance certificate for Cedar Harbor"},
                    )
                    if (
                        insurance.status_code != 200
                        or insurance.json().get("status") != "quoted_evidence"
                        or {item["source_kind"] for item in insurance.json()["citations"]}
                        != {"email", "fileos"}
                        or any(
                            "insurance certificate" not in item["quote"].casefold()
                            for item in insurance.json()["citations"]
                        )
                    ):
                        raise RuntimeError("Synthetic startup Ask quote relevance failed")
                    conflict = client.post(
                        "/v1/brain/answers",
                        json={"question": "When is Maple Arcade closing?"},
                    )
                    if conflict.status_code != 200:
                        raise RuntimeError("Synthetic startup conflict Ask failed")
                    quotes = {
                        item["source_kind"]: item["quote"]
                        for item in conflict.json().get("citations", [])
                    }
                    if (
                        conflict.json().get("status") != "quoted_evidence"
                        or "November 12, 2026" not in quotes.get("fileos", "")
                        or "November 19, 2026" not in quotes.get("email", "")
                    ):
                        raise RuntimeError("Synthetic startup conflict evidence failed")
                print(
                    "Synthetic browser-trial self-test passed: "
                    "Cedar evidence, reviewed knowledge, conflicting Maple evidence."
                )
                return 0
            url = f"http://127.0.0.1:{port}/trial#{preview.token}"
            listener = socket.create_server(("127.0.0.1", port))
            opener = threading.Timer(1.5, webbrowser.open, args=(url,))
            opener.daemon = True
            opener.start()
            print(f"Trial opening at http://127.0.0.1:{port}/trial . Stop with Ctrl-C.")
            print("Two-hour read-only trial credential stays in browser memory.")
            print("No real token is needed. Restart the launcher if the tab loses its credential.")
            try:
                config = uvicorn.Config(
                    preview.app, host="127.0.0.1", port=port, access_log=False
                )
                uvicorn.Server(config).run(sockets=[listener])
            finally:
                opener.cancel()
                listener.close()
        return 0
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
