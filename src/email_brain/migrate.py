"""Explicit administrator-only migrations with checksums and a database-wide lock."""

from __future__ import annotations

import hashlib
from pathlib import Path

import psycopg
from psycopg import sql

RUNTIME_SELECT = (
    "recovery_attempts",
    "rule_simulations",
    "rule_revisions",
    "sync_inventory",
    "sync_inventory_seals",
    "message_sync_state",
    "quarantine_receipts",
    "sync_workers",
    "sync_runs",
    "attachment_receipts",
    "intake_events",
    "tenants",
    "tenant_memberships",
    "mail_accounts",
    "sync_cursors",
    "provider_events",
    "raw_objects",
    "messages",
    "message_versions",
    "proposals",
    "proposal_evidence",
)
RUNTIME_INSERT = (
    "recovery_attempts",
    "rule_simulations",
    "rule_revisions",
    "sync_inventory",
    "sync_inventory_seals",
    "message_sync_state",
    "quarantine_receipts",
    "sync_workers",
    "sync_runs",
    "attachment_receipts",
    "intake_events",
    "sync_cursors",
    "provider_events",
    "audit_events",
    "raw_objects",
    "messages",
    "message_versions",
    "proposals",
    "proposal_evidence",
)


def migrate(dsn: str, directory: Path) -> list[str]:
    files = sorted(directory.glob("[0-9][0-9][0-9][0-9]_*.sql"))
    if not files:
        raise ValueError("migration directory is empty")
    applied: list[str] = []
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("SELECT pg_advisory_lock(713428691)")
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(name text PRIMARY KEY, sha256 text NOT NULL, applied_at timestamptz "
                "NOT NULL DEFAULT now())"
            )
            for path in files:
                content = path.read_text()
                checksum = hashlib.sha256(content.encode()).hexdigest()
                row = conn.execute(
                    "SELECT sha256 FROM schema_migrations WHERE name=%s", (path.name,)
                ).fetchone()
                if row:
                    if row[0] != checksum:
                        raise ValueError(f"applied migration checksum changed: {path.name}")
                    continue
                # These SQL files use only top-level BEGIN/COMMIT on standalone lines.
                body = "\n".join(
                    line
                    for line in content.splitlines()
                    if line.strip() not in {"BEGIN;", "COMMIT;"}
                )
                with conn.transaction():
                    conn.execute(body)
                    conn.execute(
                        "INSERT INTO schema_migrations(name,sha256) VALUES (%s,%s)",
                        (path.name, checksum),
                    )
                applied.append(path.name)
        finally:
            conn.execute("SELECT pg_advisory_unlock(713428691)")
    return applied


def grant_runtime(conn: psycopg.Connection[tuple[object, ...]], role: str) -> None:
    """Administrator operation; no ownership or role membership is granted."""
    conn.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role)))
    for privilege, tables in (
        ("SELECT", RUNTIME_SELECT),
        ("INSERT", RUNTIME_INSERT),
        ("UPDATE", ("messages", "sync_cursors", "proposals", "sync_workers", "message_sync_state")),
    ):
        conn.execute(
            sql.SQL("GRANT {} ON {} TO {}").format(
                sql.SQL(privilege),
                sql.SQL(",").join(map(sql.Identifier, tables)),
                sql.Identifier(role),
            )
        )
