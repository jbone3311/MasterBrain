"""Local prototype commands. No live provider or model credentials are used by the demo."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import psycopg
import uvicorn
from psycopg import sql

from email_brain.api import create_app
from email_brain.auth import Authenticator, Credential, TokenRegistry
from email_brain.browser_auth import BrowserAuth, BrowserConfig
from email_brain.browser_operator import tls_options
from email_brain.document_controller import run_document_controller
from email_brain.domain.models import TenantContext
from email_brain.fastmail_enrollment import run_fastmail_enrollment
from email_brain.migrate import grant_runtime, migrate
from email_brain.oidc import AccessTokenVerifier, OIDCAuthenticator, OIDCConfig
from email_brain.processing_controller import private_bytes, run_controller, shutdown_signals
from email_brain.read_controller import run_read_controller
from email_brain.store import IngestItem, Store
from email_brain.synthetic import fake_email
from email_brain.synthetic_mailbox import MailboxSpec, export_mailbox, seed_mailbox
from email_brain.tenant_db import TenantDbRoutes
from masterbrain.datacore.fileos import snapshot_tree
from masterbrain.datacore.persistence import DataCoreStore
from masterbrain.knowledge import KnowledgeCore
from masterbrain.knowledge_schema import ProjectWrite

_DEMO_FILE_TEXT = (
    "Cedar Harbor fictional planning brief. The October review joins email and files.\n"
)
_DEMO_REVISION = "synthetic-masterbrain-demo-v1"


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


def provision_demo(state: Path, *, masterbrain: bool = False) -> None:
    if not state.is_absolute() or state.is_symlink() or "Dropbox" in state.parts:
        raise ValueError("state must use an absolute path outside Dropbox")
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    if "Dropbox" in state.resolve(strict=True).parts or state.stat().st_mode & 0o077:
        raise ValueError("state must be private and outside Dropbox")
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
    scopes = [
        "email.search", "email.evidence.read", "email.proposal.create",
        "email.proposal.read", "email.review",
    ]
    if masterbrain:
        scopes += [
            "brain.search", "brain.evidence.read", "brain.content.read",
            "brain.changes.read", "knowledge.search", "knowledge.read",
            "knowledge.changes.read", "knowledge.review",
        ]
    credential = [
        {
            "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
            "tenant_id": str(tenant_id),
            "actor_id": str(actor_id),
            "scopes": scopes,
            "client_kind": "human",
            "expires_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
        }
    ]
    TokenRegistry([Credential.model_validate(item) for item in credential])
    _private_file(state / "credentials.json", json.dumps(credential, indent=2))
    _private_file(state / "owner-token.txt", token)
    _private_file(
        state / "demo.json",
        json.dumps(
            {"tenant_id": str(tenant_id), "actor_id": str(actor_id), "account_id": str(account_id)}
        ),
    )
    if masterbrain:
        _private_file(state / "masterbrain-demo.marker", _DEMO_REVISION + "\n")
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
        ctx, UUID(data["account_id"]), None, "synthetic-complete-v1", items, synthetic_only=True
    )
    print(f"Synthetic page committed: {count} new events (replays are no-ops).")


def seed_masterbrain(state: Path) -> None:
    """Replay-safe fictional Email/FileOS fixture through shared DataCore."""
    marker = state / "masterbrain-demo.marker"
    if (not state.is_absolute() or state.is_symlink()
            or "Dropbox" in state.resolve(strict=True).parts
            or state.stat().st_mode & 0o077
            or not marker.is_file() or marker.is_symlink()
            or marker.read_text() != _DEMO_REVISION + "\n"):
        raise ValueError("fresh private MasterBrain demo state required")
    data = json.loads((state / "demo.json").read_text())
    tenant_id, actor_id, account_id = (
        UUID(data["tenant_id"]), UUID(data["actor_id"]), UUID(data["account_id"]),
    )
    store = Store(_env("EMAIL_BRAIN_DSN"))
    ctx = TenantContext(
        tenant_id, actor_id,
        frozenset({
            "brain.source.ingest", "brain.document.publish", "brain.search",
            "brain.index.activate", "knowledge.review",
        }),
        uuid4(),
    )
    with store.transaction(ctx) as conn:
        exact_demo = conn.execute(
            "SELECT 1 FROM tenants t JOIN mail_accounts a ON a.tenant_id=t.id "
            "WHERE t.id=%s AND t.name='Synthetic demo' AND a.id=%s "
            "AND a.provider='fastmail' AND a.address='owner@example.invalid' "
            "AND a.secret_ref='synthetic:no-token' "
            "AND a.provider_account_id IS NULL AND a.status='active'",
            (tenant_id, account_id),
        ).fetchone()
        if exact_demo is None:
            raise ValueError("combined seed requires the exact fictional demo account")
    seed(state)
    core = DataCoreStore(store)
    plan = core.email_bridge_plan(ctx, account_id)
    if len(plan["results"]) != 3 or plan["next_cursor"] is not None:
        raise ValueError("fictional Email demo source is incomplete")
    bridged = [
        core.bridge_current_email_version(
            ctx, UUID(row["legacy_version_id"]),
            uuid5(NAMESPACE_URL, f"masterbrain-demo:{tenant_id}:{row['legacy_version_id']}"),
            code_revision=_DEMO_REVISION, expected_account_id=account_id,
        )
        for row in plan["results"]
    ]
    root = state / "fictional-files"
    if root.is_symlink():
        raise ValueError("fictional FileOS demo root must not be a symlink")
    root.mkdir(mode=0o700, exist_ok=True)
    if root.stat().st_mode & 0o077:
        raise ValueError("fictional FileOS demo root must be private")
    file = root / "cedar-harbor-brief.txt"
    if not file.exists():
        _private_file(file, _DEMO_FILE_TEXT)
    if file.is_symlink() or file.read_text() != _DEMO_FILE_TEXT:
        raise ValueError("fictional FileOS demo source changed")
    manifest = snapshot_tree(
        root, source_id="files_demo",
        observed_at=datetime(2026, 9, 22, 12, tzinfo=UTC),
    )
    if (len(manifest["items"]) != 1
            or manifest["items"][0]["locator"] != file.name
            or manifest["errors"]):
        raise ValueError("fictional FileOS demo snapshot is incomplete")
    file_run_id = uuid5(NAMESPACE_URL, f"masterbrain-demo-file:{tenant_id}")
    core.import_fileos_snapshot(ctx, manifest, file_run_id)
    published = core.publish_text(
        ctx, manifest["items"][0]["version_id"], _DEMO_FILE_TEXT,
        code_revision=_DEMO_REVISION,
    )
    receipt = core.complete_fileos_run(
        ctx, manifest, file_run_id, outcomes={"extracted": 1},
        item_outcomes={manifest["items"][0]["item_id"]: "extracted"},
        published_documents=1, code_revision=_DEMO_REVISION,
        document_processor_version=None,
    )
    generation = core.build_fileos_index_generation(
        ctx, "files_demo", receipt.run_id, code_revision=_DEMO_REVISION,
    )
    core.activate_fileos_index_generation(
        ctx, "files_demo", generation.generation_id,
        uuid5(NAMESPACE_URL, f"masterbrain-demo-index:{tenant_id}"),
    )
    project = KnowledgeCore(store).publish(
        ctx,
        ProjectWrite(
            kind="project", title="Cedar Harbor fictional project",
            description="Fictional cross-source demonstration only", state="active",
            evidence_ids=[bridged[0].evidence_id, published.evidence_id],
            source_quote="Cedar Harbor fictional planning brief",
            confidence=1.0, observed_at=datetime(2026, 9, 22, 12, tzinfo=UTC),
            reviewed=True,
        ),
        uuid5(NAMESPACE_URL, f"masterbrain-demo-project:{tenant_id}"),
    )
    print(f"Fictional MasterBrain Email/FileOS project ready: {project.object_id}.")


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
        synthetic = conn.execute(
            "SELECT 1 FROM mail_accounts WHERE id=%s AND provider_account_id IS NULL "
            "AND secret_ref LIKE %s AND status='active'",
            (account, "synthetic:%"),
        ).fetchone()
        if not synthetic:
            raise ValueError("unenrolled synthetic account required")
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
        store.ingest_page(ctx, account, cursor, next_cursor, items, synthetic_only=True)
        position, cursor = stop, next_cursor
    print(f"Synthetic corpus ready: {count} fictional messages; no provider or model contacted.")


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="email-brain")
    commands = parser.add_subparsers(dest="command", required=True)
    migration = commands.add_parser("migrate", help="Administrator-only schema migration")
    migration.add_argument("--directory", type=Path, default=Path("migrations"))
    migration.add_argument(
        "--allow-populated-rewrite",
        action="store_true",
        help=(
            "Explicitly permit the lock-heavy 0008/0009 rewrites "
            "after a reviewed maintenance plan"
        ),
    )
    for command in ("init-demo", "seed-demo", "init-masterbrain-demo", "seed-masterbrain-demo"):
        commands.add_parser(command).add_argument("--state-dir", type=Path, required=True)
    corpus = commands.add_parser("seed-corpus", help="Import fictional emails, no provider calls")
    corpus.add_argument("--state-dir", type=Path, required=True)
    corpus.add_argument("--count", type=int, default=256)
    source = commands.add_parser(
        "fastmail-source", help="Owner-reviewed local Fastmail scope enrollment/disconnect"
    )
    source.add_argument("--config", type=Path, required=True)
    source_actions = source.add_mutually_exclusive_group(required=True)
    source_actions.add_argument("--check", action="store_true")
    source_actions.add_argument("--enroll", action="store_true")
    source_actions.add_argument("--disconnect", action="store_true")
    source.add_argument("--confirm-account", type=UUID)
    source.add_argument("--confirm-scope")
    source.add_argument("--confirm-binding")
    serve = commands.add_parser("serve", help="Loopback-only developer server")
    serve.add_argument("--port", type=int, default=8080)
    serve.add_argument("--oidc-config", type=Path, default=None)
    serve.add_argument("--browser-config", type=Path, default=None)
    serve.add_argument("--tenant-db-config", type=Path, default=None)
    serve.add_argument("--tls-cert", type=Path, default=None)
    serve.add_argument("--tls-key", type=Path, default=None)
    serve.add_argument(
        "--check", action="store_true", help="Browser configuration/TLS preflight only"
    )
    serve.add_argument("--recovery-parser-version", default=None)
    serve.add_argument("--document-processor-version", default=None)
    for name, help_text in (
        ("process-jobs", "Run explicitly approved MIME recovery jobs"),
        ("process-documents", "Run explicitly approved synthetic PDF jobs"),
        ("sync-read", "Explicit bounded reads for an already enrolled Fastmail account"),
    ):
        processing = commands.add_parser(name, help=help_text)
        processing.add_argument("--config", type=Path, required=True)
        processing.add_argument("--check", action="store_true")
        processing.add_argument("--max-iterations", type=int, default=1)
        processing.add_argument("--idle-seconds", type=int, default=5)
        processing.add_argument("--tenant-bound-db", action="store_true")
        if name == "sync-read":
            processing.add_argument("--allow-provider-read", action="store_true")
    for name in ("export-test-mailbox", "seed-test-mailbox"):
        fixture_command = commands.add_parser(
            name, help="Known-answer fictional mail; no live delivery"
        )
        fixture_command.add_argument("--seed", type=int, default=42)
        fixture_command.add_argument("--projects", type=int, default=3)
        if name == "export-test-mailbox":
            fixture_command.add_argument("--output-dir", type=Path, required=True)
        else:
            fixture_command.add_argument("--state-dir", type=Path, required=True)
            fixture_command.add_argument("--max-events", type=int, default=100)
            fixture_command.add_argument("--interval-seconds", type=int, default=0)
    args = parser.parse_args(argv)
    try:
        if args.command == "migrate":
            print(
                "Applied:",
                migrate(
                    _env("EMAIL_BRAIN_ADMIN_DSN"),
                    args.directory,
                    allow_populated_rewrite=args.allow_populated_rewrite,
                ),
            )
        elif args.command == "init-demo":
            provision_demo(args.state_dir)
        elif args.command == "init-masterbrain-demo":
            provision_demo(args.state_dir, masterbrain=True)
        elif args.command == "seed-demo":
            seed(args.state_dir)
        elif args.command == "seed-masterbrain-demo":
            seed_masterbrain(args.state_dir)
        elif args.command == "seed-corpus":
            seed_corpus(args.state_dir, args.count)
        elif args.command == "export-test-mailbox":
            print(
                json.dumps(export_mailbox(args.output_dir, MailboxSpec(args.seed, args.projects)))
            )
        elif args.command == "seed-test-mailbox":
            spec = MailboxSpec(args.seed, args.projects)
            data = json.loads(private_bytes(args.state_dir / "demo.json"))
            if (
                not isinstance(data, dict)
                or set(data) != {"tenant_id", "actor_id", "account_id"}
                or any(not isinstance(value, str) for value in data.values())
            ):
                raise ValueError("invalid synthetic state")
            ctx = TenantContext(
                UUID(data["tenant_id"]),
                UUID(data["actor_id"]),
                frozenset({"email.ingest"}),
                uuid4(),
            )
            stop = Event()
            with shutdown_signals(stop):
                result = seed_mailbox(
                    Store(_env("EMAIL_BRAIN_DSN")),
                    ctx,
                    UUID(data["account_id"]),
                    spec,
                    max_events=args.max_events,
                    interval_seconds=args.interval_seconds,
                    stop=stop,
                )
            print(json.dumps(result, sort_keys=True))
        elif args.command == "sync-read":
            stop = Event()
            with shutdown_signals(stop):
                result = run_read_controller(
                    args.config,
                    _env("EMAIL_BRAIN_DSN"),
                    check=args.check,
                    allow_provider_read=args.allow_provider_read,
                    max_iterations=args.max_iterations,
                    idle_seconds=args.idle_seconds,
                    stop=stop,
                    tenant_bound_db=args.tenant_bound_db,
                )
            print(json.dumps(result, sort_keys=True))
            if result.get("attention_required"):
                parser.exit(2, "Read worker paused; operator attention required.\n")
        elif args.command == "fastmail-source":
            action: Literal["check", "enroll", "disconnect"] = (
                "check" if args.check else "enroll" if args.enroll else "disconnect"
            )
            print(
                json.dumps(
                    run_fastmail_enrollment(
                        args.config,
                        _env("EMAIL_BRAIN_ADMIN_DSN"),
                        action=action,
                        confirmed_account_id=args.confirm_account,
                        confirmed_scope_sha256=args.confirm_scope,
                        confirmed_binding_sha256=args.confirm_binding,
                    ),
                    sort_keys=True,
                )
            )
        elif args.command in {"process-jobs", "process-documents"}:
            stop = Event()
            controller = (
                run_controller if args.command == "process-jobs" else run_document_controller
            )
            with shutdown_signals(stop):
                result = controller(
                    args.config,
                    _env("EMAIL_BRAIN_DSN"),
                    check=args.check,
                    max_iterations=args.max_iterations,
                    idle_seconds=args.idle_seconds,
                    stop=stop,
                    tenant_bound_db=args.tenant_bound_db,
                )
            print(json.dumps(result, sort_keys=True))
        else:
            routes = (
                TenantDbRoutes.from_file(args.tenant_db_config)
                if args.tenant_db_config is not None
                else None
            )
            store = (
                Store(routes.identity_dsn, tenant_dsns=routes.tenant_dsns)
                if routes is not None
                else Store(_env("EMAIL_BRAIN_DSN"))
            )
            registry: Authenticator
            browser_auth = None
            tls = {}
            if args.browser_config is not None:
                if args.oidc_config is not None or os.environ.get("EMAIL_BRAIN_CREDENTIALS_FILE"):
                    raise ValueError("select exactly one authentication mode")
                if args.tls_cert is None or args.tls_key is None:
                    raise ValueError("browser mode requires explicit TLS files")
                config = BrowserConfig.from_file(args.browser_config)
                tls = tls_options(config, args.port, args.tls_cert, args.tls_key)
                if args.check:
                    print(
                        json.dumps(
                            {
                                "mode": "browser",
                                "status": "configuration_valid",
                                "database_checked": False,
                                "network_contact": False,
                            },
                            sort_keys=True,
                        )
                    )
                    return
                registry = OIDCAuthenticator(store, AccessTokenVerifier(config.identity))
                browser_auth = BrowserAuth(config, registry)
            elif args.tls_cert is not None or args.tls_key is not None or args.check:
                raise ValueError("TLS and check options require browser mode")
            elif args.oidc_config is not None:
                if os.environ.get("EMAIL_BRAIN_CREDENTIALS_FILE"):
                    raise ValueError("select exactly one authentication mode")
                registry = OIDCAuthenticator(
                    store, AccessTokenVerifier(OIDCConfig.from_file(args.oidc_config))
                )
            else:
                registry = TokenRegistry.from_file(Path(_env("EMAIL_BRAIN_CREDENTIALS_FILE")))
            app = create_app(
                store,
                registry,
                recovery_parser_version=args.recovery_parser_version,
                document_processor_version=args.document_processor_version,
                browser_auth=browser_auth,
            )
            uvicorn.run(
                app, host="127.0.0.1", port=args.port, access_log=False, proxy_headers=False, **tls
            )
    except (ValueError, OSError, RecursionError, psycopg.Error):
        # Do not echo exception contents: a DSN or SQL error can contain credentials.
        parser.exit(
            1,
            "Operation failed. Check configuration, permissions and service availability. "
            "Sensitive exception details suppressed.\n",
        )


if __name__ == "__main__":
    main()
