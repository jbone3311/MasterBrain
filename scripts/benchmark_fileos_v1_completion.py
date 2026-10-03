#!/usr/bin/env python3
"""Opt-in, synthetic PostgreSQL benchmark of the ADR-122 ledger-trigger cost.

Only run against a new disposable database named email_brain_test_benchmark_*.
The comparison adds the old deferred per-item check to today's schema; it
isolates that check's cost, not every historical pre-0043 implementation detail.
"""

from __future__ import annotations

import argparse
import json
import secrets
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from email_brain.domain.models import TenantContext
from email_brain.migrate import grant_runtime, migrate
from email_brain.store import Store
from masterbrain.datacore.fileos import snapshot_tree
from masterbrain.datacore.persistence import DataCoreStore

ROOT = Path(__file__).resolve().parents[1]
LEGACY_TRIGGER = """
CREATE CONSTRAINT TRIGGER fileos_run_item_ledger
AFTER INSERT ON public.brain_fileos_run_items
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
EXECUTE FUNCTION public.enforce_fileos_run_item_ledger()
"""


def validate_target(dsn: str, rows: int) -> None:
    dbname = conninfo_to_dict(dsn).get("dbname", "")
    if not isinstance(dbname, str) or not dbname.startswith("email_brain_test_benchmark_"):
        raise ValueError("refusing a non-benchmark database")
    if not 1 <= rows <= 3_000:
        raise ValueError("rows must be between 1 and 3000")
    with psycopg.connect(dsn) as conn:
        existing = conn.execute(
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','S','f')"
        ).fetchone()
        if existing and existing[0]:
            raise ValueError("benchmark database must be new and empty")


def checkpoint_count(dsn: str) -> int:
    with psycopg.connect(dsn) as conn:
        row = conn.execute(
            "SELECT num_timed+num_requested FROM pg_stat_checkpointer"
        ).fetchone()
        assert row is not None
        return int(row[0])


def run(dsn: str, rows: int) -> dict[str, object]:
    validate_target(dsn, rows)
    migrate(dsn, ROOT / "migrations")
    role = "benchmark_runtime_" + uuid4().hex[:12]
    password = secrets.token_urlsafe(32)
    tenant_id, actor_id = uuid4(), uuid4()
    trigger_installed = False
    with psycopg.connect(dsn) as conn:
        conn.execute(
            sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD {}").format(
                sql.Identifier(role), sql.Literal(password)
            )
        )
        grant_runtime(conn, role)
        conn.execute("INSERT INTO tenants(id,name) VALUES (%s,'Synthetic benchmark')", (tenant_id,))
        conn.execute(
            "INSERT INTO tenant_memberships(tenant_id,user_id,role) "
            "VALUES (%s,%s,'owner')",
            (tenant_id, actor_id),
        )
    try:
        runtime = Store(make_conninfo(dsn, user=role, password=password))
        core = DataCoreStore(runtime)
        ctx = TenantContext(
            tenant_id,
            actor_id,
            frozenset({"brain.source.ingest", "brain.document.publish"}),
            uuid4(),
        )
        with tempfile.TemporaryDirectory(prefix="masterbrain-synthetic-benchmark-") as name:
            root = Path(name)
            for index in range(rows):
                (root / f"fictional-{index:04d}.txt").write_bytes(
                    f"Fictional benchmark row {index}\n".encode()
                )
            manifests = {
                mode: snapshot_tree(
                    root,
                    source_id=f"benchmark_{mode}",
                    observed_at=datetime(2026, 9, 22, tzinfo=UTC),
                )
                for mode in ("current", "legacy_trigger")
            }
            runs = {mode: uuid4() for mode in manifests}
            for mode, manifest in manifests.items():
                assert len(manifest["items"]) == rows
                core.import_fileos_snapshot(ctx, manifest, runs[mode])
            checkpoints_before = checkpoint_count(dsn)

            def complete(mode: str) -> float:
                manifest = manifests[mode]
                started = perf_counter()
                core.complete_fileos_run(
                    ctx,
                    manifest,
                    runs[mode],
                    outcomes={"unsupported": rows},
                    item_outcomes={item["item_id"]: "unsupported" for item in manifest["items"]},
                    published_documents=0,
                    code_revision="synthetic-completion-benchmark",
                    document_processor_version=None,
                )
                elapsed = perf_counter() - started
                with runtime.transaction(ctx) as conn:
                    count = conn.execute(
                        "SELECT count(*) AS n FROM brain_fileos_run_items "
                        "WHERE actor_id=%s AND run_id=%s",
                        (actor_id, runs[mode]),
                    ).fetchone()
                    assert count and count["n"] == rows
                return elapsed

            current_seconds = complete("current")
            checkpoints_after_current = checkpoint_count(dsn)
            with psycopg.connect(dsn) as conn:
                conn.execute(LEGACY_TRIGGER)
            trigger_installed = True
            legacy_seconds = complete("legacy_trigger")
            checkpoints_after_legacy = checkpoint_count(dsn)
        with psycopg.connect(dsn) as conn:
            version = conn.execute("SHOW server_version").fetchone()
        assert version is not None
        return {
            "rows_per_run": rows,
            "postgres_version": version[0],
            "current_seconds": round(current_seconds, 3),
            "current_plus_legacy_trigger_seconds": round(legacy_seconds, 3),
            "legacy_trigger_ratio": round(legacy_seconds / current_seconds, 2),
            "checkpoints_during_current": checkpoints_after_current - checkpoints_before,
            "checkpoints_during_legacy": checkpoints_after_legacy - checkpoints_after_current,
            "order": ["current", "current_plus_legacy_trigger"],
            "comparison": "same current schema and writer, old per-item deferred trigger added",
        }
    finally:
        with psycopg.connect(dsn) as conn:
            if trigger_installed:
                conn.execute("DROP TRIGGER fileos_run_item_ledger ON public.brain_fileos_run_items")
            conn.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(role)))
            conn.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admin-dsn", required=True, help="fresh disposable benchmark database")
    parser.add_argument("--rows", type=int, default=3_000)
    args = parser.parse_args()
    try:
        result = run(args.admin_dsn, args.rows)
    except (psycopg.Error, ValueError):
        raise SystemExit("benchmark refused or database unavailable") from None
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
