"""Explicit administrator-only migrations with checksums and a database-wide lock."""

from __future__ import annotations

import hashlib
from pathlib import Path

import psycopg
from psycopg import sql

RUNTIME_SELECT = (
    "knowledge_entities",
    "knowledge_entity_aliases",
    "knowledge_relationships",
    "knowledge_claims",
    "knowledge_projects",
    "knowledge_events",
    "knowledge_commitments",
    "knowledge_corrections",
    "knowledge_evidence",
    "knowledge_search_documents",
    "knowledge_change_events",
    "knowledge_receipts",
    "brain_sources",
    "brain_source_items",
    "brain_source_versions",
    "brain_evidence",
    "brain_normalized_documents",
    "brain_chunks",
    "brain_provenance",
    "brain_provenance_inputs",
    "brain_change_events",
    "brain_jobs",
    "brain_import_receipts",
    "brain_email_bridge_receipts",
    "brain_parts",
    "brain_email_attachment_bridge_receipts",
    "brain_email_document_bridge_receipts",
    "brain_archive_inventories",
    "brain_archive_members",
    "brain_archive_skips",
    "brain_archive_inventory_receipts",
    "brain_fileos_run_receipts",
    "brain_fileos_run_items",
    "brain_fileos_absence_events",
    "brain_index_generations",
    "brain_index_generation_items",
    "brain_index_generation_chunks",
    "brain_index_generation_receipts",
    "brain_index_activations",
    "memory_records",
    "memory_revisions",
    "memory_receipts",
    "external_identities",
    "document_jobs",
    "document_extractions",
    "recovery_jobs",
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
    "knowledge_entities",
    "knowledge_entity_aliases",
    "knowledge_relationships",
    "knowledge_claims",
    "knowledge_projects",
    "knowledge_events",
    "knowledge_commitments",
    "knowledge_corrections",
    "knowledge_evidence",
    "knowledge_search_documents",
    "knowledge_change_events",
    "knowledge_receipts",
    "brain_sources",
    "brain_source_items",
    "brain_source_versions",
    "brain_evidence",
    "brain_normalized_documents",
    "brain_chunks",
    "brain_provenance",
    "brain_provenance_inputs",
    "brain_change_events",
    "brain_jobs",
    "brain_import_receipts",
    "brain_email_bridge_receipts",
    "brain_parts",
    "brain_email_attachment_bridge_receipts",
    "brain_email_document_bridge_receipts",
    "brain_archive_inventories",
    "brain_archive_members",
    "brain_archive_skips",
    "brain_archive_inventory_receipts",
    "brain_fileos_run_receipts",
    "brain_fileos_run_items",
    "brain_fileos_absence_events",
    "brain_index_generations",
    "brain_index_generation_items",
    "brain_index_generation_chunks",
    "brain_index_generation_receipts",
    "brain_index_activations",
    "memory_records",
    "memory_revisions",
    "memory_receipts",
    "document_jobs",
    "document_extractions",
    "recovery_jobs",
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
    conn.execute(
        sql.SQL("GRANT EXECUTE ON FUNCTION lock_recovery_owners(uuid,uuid,uuid) TO {}").format(
            sql.Identifier(role)
        )
    )
    for privilege, tables in (
        ("SELECT", RUNTIME_SELECT),
        ("INSERT", RUNTIME_INSERT),
        (
            "UPDATE",
            (
                "messages",
                "sync_cursors",
                "proposals",
                "sync_workers",
                "message_sync_state",
                "recovery_jobs",
                "document_jobs",
                "brain_sources",
                "brain_source_items",
                "brain_jobs",
            ),
        ),
    ):
        conn.execute(
            sql.SQL("GRANT {} ON {} TO {}").format(
                sql.SQL(privilege),
                sql.SQL(",").join(map(sql.Identifier, tables)),
                sql.Identifier(role),
            )
        )
