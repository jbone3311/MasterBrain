"""Explicit administrator-only migrations with checksums and a database-wide lock."""

from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import UUID

import psycopg
from psycopg import sql

RUNTIME_SELECT = (
    "knowledge_entities",
    "knowledge_entity_aliases",
    "knowledge_project_aliases",
    "knowledge_relationships",
    "knowledge_claims",
    "knowledge_projects",
    "knowledge_project_members",
    "knowledge_project_artifacts",
    "knowledge_project_artifact_receipts",
    "knowledge_events",
    "knowledge_commitments",
    "knowledge_corrections",
    "knowledge_evidence",
    "knowledge_search_documents",
    "knowledge_change_events",
    "knowledge_receipts",
    "knowledge_statement_proposals",
    "knowledge_statement_rows",
    "knowledge_statement_receipts",
    "knowledge_statement_fileos_replays",
    "knowledge_proposal_batches",
    "knowledge_proposals",
    "knowledge_proposal_evidence",
    "knowledge_proposal_decisions",
    "knowledge_proposal_review_receipts",
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
    "brain_archive_member_text_receipts",
    "brain_archive_member_document_receipts",
    "brain_archive_member_image_receipts",
    "brain_fileos_run_receipts",
    "brain_fileos_run_items",
    "brain_fileos_absence_events",
    "brain_fileos_transition_packets",
    "brain_fileos_v2_staged_inventories",
    "brain_fileos_v2_staged_rows",
    "brain_fileos_v2_transition_approvals",
    "brain_fileos_v2_baseline_verifications",
    "brain_fileos_v2_evidence_preparations",
    "brain_fileos_v2_prepared_rows",
    "brain_fileos_v2_baseline_authorizations",
    "brain_fileos_v2_baseline_completions",
    "brain_fileos_v2_document_attempts",
    "brain_fileos_v2_document_attempt_items",
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
    "knowledge_project_aliases",
    "knowledge_relationships",
    "knowledge_claims",
    "knowledge_projects",
    "knowledge_project_members",
    "knowledge_project_artifacts",
    "knowledge_project_artifact_receipts",
    "knowledge_events",
    "knowledge_commitments",
    "knowledge_corrections",
    "knowledge_evidence",
    "knowledge_search_documents",
    "knowledge_change_events",
    "knowledge_receipts",
    "knowledge_statement_proposals",
    "knowledge_statement_rows",
    "knowledge_statement_receipts",
    "knowledge_statement_fileos_replays",
    "knowledge_proposal_batches",
    "knowledge_proposals",
    "knowledge_proposal_evidence",
    "knowledge_proposal_decisions",
    "knowledge_proposal_review_receipts",
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
    "brain_archive_member_text_receipts",
    "brain_archive_member_document_receipts",
    "brain_archive_member_image_receipts",
    "brain_fileos_run_receipts",
    "brain_fileos_run_items",
    "brain_fileos_absence_events",
    "brain_fileos_transition_packets",
    "brain_fileos_v2_staged_inventories",
    "brain_fileos_v2_staged_rows",
    "brain_fileos_v2_transition_approvals",
    "brain_fileos_v2_baseline_verifications",
    "brain_fileos_v2_evidence_preparations",
    "brain_fileos_v2_prepared_rows",
    "brain_fileos_v2_baseline_authorizations",
    "brain_fileos_v2_baseline_completions",
    "brain_fileos_v2_document_attempts",
    "brain_fileos_v2_document_attempt_items",
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

POPULATED_REWRITE_TABLES = {
    "0008_quarantine_recovery.sql": "message_versions",
    "0009_external_raw_evidence.sql": "raw_objects",
}


def _guard_populated_rewrite(
    conn: psycopg.Connection[tuple[object, ...]], migration_name: str
) -> None:
    """Refuse legacy heap rewrites on populated tables without an explicit rollout."""
    table = POPULATED_REWRITE_TABLES.get(migration_name)
    if table is None:
        return
    # A concurrent reader may allow SHARE but block the ALTER's stronger lock.
    # Bound that upgrade too; the explicit maintenance override keeps its own
    # operator-chosen lock budget.
    conn.execute("SET LOCAL lock_timeout = '5s'")
    # SHARE permits readers but fences concurrent inserts between the check and
    # the ALTER TABLE. NOWAIT turns a busy writer into a safe, immediate refusal.
    conn.execute(
        sql.SQL("LOCK TABLE public.{} IN SHARE MODE NOWAIT").format(sql.Identifier(table))
    )
    if conn.execute(
        sql.SQL("SELECT EXISTS (SELECT 1 FROM public.{} LIMIT 1)").format(sql.Identifier(table))
    ).fetchone() == (True,):
        raise ValueError(
            f"{migration_name} rewrites populated {table}; "
            "use an operator-reviewed maintenance path or "
            "--allow-populated-rewrite after a backup and lock-budget review"
        )


def migrate(
    dsn: str, directory: Path, *, allow_populated_rewrite: bool = False
) -> list[str]:
    if type(allow_populated_rewrite) is not bool:
        raise ValueError("allow_populated_rewrite must be boolean")
    files = sorted(directory.glob("[0-9][0-9][0-9][0-9]_*.sql"))
    if not files:
        raise ValueError("migration directory is empty")
    applied: list[str] = []
    with psycopg.connect(dsn, autocommit=True) as conn:
        migration_role = conn.execute(
            "SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user"
        ).fetchone()
        if not migration_role or not (migration_role[0] or migration_role[1]):
            raise ValueError("migrations require superuser or BYPASSRLS role")
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
                    if not allow_populated_rewrite:
                        _guard_populated_rewrite(conn, path.name)
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
    resolver_row = conn.execute(
        "SELECT to_regprocedure('public.resolve_external_identity(text,text,text)') IS NOT NULL"
    ).fetchone()
    if resolver_row is None:
        raise ValueError("cannot inspect identity resolver migration")
    has_resolver = bool(resolver_row[0])
    if has_resolver:
        conn.execute(
            sql.SQL("REVOKE SELECT ON public.external_identities FROM {}").format(
                sql.Identifier(role)
            )
        )
        if conn.execute(
            "SELECT has_table_privilege(%s,'public.external_identities','SELECT')",
            (role,),
        ).fetchone() == (True,):
            raise ValueError("runtime identity-table SELECT remains inherited")
        conn.execute(
            sql.SQL(
                "GRANT EXECUTE ON FUNCTION public.resolve_external_identity(text,text,text) TO {}"
            ).format(sql.Identifier(role))
        )
        if conn.execute(
            "SELECT to_regprocedure('public.resolve_external_identity_v2(text,text,text)') "
            "IS NOT NULL"
        ).fetchone() == (True,):
            conn.execute(
                sql.SQL(
                    "GRANT EXECUTE ON FUNCTION "
                    "public.resolve_external_identity_v2(text,text,text) TO {}"
                ).format(sql.Identifier(role))
            )
    conn.execute(
        sql.SQL("GRANT EXECUTE ON FUNCTION lock_recovery_owners(uuid,uuid,uuid) TO {}").format(
            sql.Identifier(role)
        )
    )
    for privilege, tables in (
        (
            "SELECT",
            tuple(t for t in RUNTIME_SELECT if t != "external_identities")
            if has_resolver
            else RUNTIME_SELECT,
        ),
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


def grant_tenant_runtime(
    conn: psycopg.Connection[tuple[object, ...]], role: str, tenant_id: UUID
) -> None:
    """DBA-only, atomic opt-in to one-login/one-tenant RLS containment."""
    if not isinstance(role, str) or not role or not isinstance(tenant_id, UUID):
        raise ValueError("invalid tenant runtime enrollment")
    with conn.transaction():
        operator = conn.execute(
            "SELECT rolsuper FROM pg_roles WHERE rolname=current_user"
        ).fetchone()
        candidate = conn.execute(
            "SELECT rolcanlogin,rolsuper,rolbypassrls,rolcreatedb,rolcreaterole,"
            "rolreplication FROM pg_roles WHERE rolname=%s",
            (role,),
        ).fetchone()
        if (
            not operator
            or not operator[0]
            or not candidate
            or candidate != (True, False, False, False, False, False)
        ):
            raise ValueError("unsafe tenant runtime database role")
        if conn.execute(
            "SELECT EXISTS(SELECT 1 FROM pg_roles r WHERE "
            "pg_has_role((SELECT oid FROM pg_roles WHERE rolname=%s),r.oid,'member') "
            "AND (r.rolsuper OR r.rolbypassrls OR r.rolcreaterole "
            "OR EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n "
            "ON n.oid=c.relnamespace WHERE c.relowner=r.oid "
            "AND n.nspname='public' AND c.relkind='r'))) ",
            (role,),
        ).fetchone() != (False,):
            raise ValueError("tenant runtime role inherits unsafe authority")
        if conn.execute(
            "SELECT pg_has_role(%s,'masterbrain_identity_admin','member')",
            (role,),
        ).fetchone() != (False,):
            raise ValueError("tenant runtime role has identity administration")
        if conn.execute(
            "SELECT to_regprocedure('public.masterbrain_tenant_login_allows(uuid)') IS NOT NULL"
        ).fetchone() != (True,):
            raise ValueError("tenant-login fence migration is missing")
        uncovered = conn.execute(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relkind='r' AND "
            "(c.relname='tenants' OR EXISTS (SELECT 1 FROM pg_attribute a "
            "WHERE a.attrelid=c.oid AND a.attname='tenant_id' AND a.attnum>0)) "
            "AND (NOT c.relrowsecurity OR NOT c.relforcerowsecurity "
            "OR NOT EXISTS (SELECT 1 FROM pg_policy p "
            "WHERE p.polrelid=c.oid AND p.polname='tenant_login_fence' "
            "AND NOT p.polpermissive)) LIMIT 1"
        ).fetchone()
        if uncovered:
            raise ValueError("tenant-login RLS fence inventory is incomplete")
        existing = conn.execute(
            "SELECT tenant_id FROM public.masterbrain_tenant_login_bindings WHERE role_name=%s",
            (role,),
        ).fetchone()
        if existing and existing[0] != tenant_id:
            raise ValueError("tenant runtime role is already bound")
        if (
            not existing
            and conn.execute(
                "SELECT 1 FROM public.audit_events WHERE event_type='tenant_login.insert' "
                "AND resource_type='database_role' AND resource_id=%s LIMIT 1",
                (role,),
            ).fetchone()
        ):
            raise ValueError("previously bound runtime role cannot be reused")
        grant_runtime(conn, role)
        if not existing:
            conn.execute(
                "INSERT INTO public.masterbrain_tenant_login_bindings(role_name,tenant_id) "
                "VALUES (%s,%s)",
                (role, tenant_id),
            )
        conn.execute(
            sql.SQL(
                "GRANT masterbrain_tenant_runtime TO {} WITH ADMIN FALSE, INHERIT FALSE, SET FALSE"
            ).format(sql.Identifier(role))
        )


def grant_identity_lookup(conn: psycopg.Connection[tuple[object, ...]], role: str) -> None:
    """DBA-only provisioning of a clean login with exact identity lookup authority."""
    if not isinstance(role, str) or not role:
        raise ValueError("invalid identity lookup role")
    with conn.transaction():
        operator = conn.execute(
            "SELECT rolsuper FROM pg_roles WHERE rolname=current_user"
        ).fetchone()
        candidate = conn.execute(
            "SELECT rolcanlogin,rolsuper,rolbypassrls,rolcreatedb,rolcreaterole,"
            "rolreplication FROM pg_roles WHERE rolname=%s",
            (role,),
        ).fetchone()
        if (
            not operator
            or not operator[0]
            or candidate != (True, False, False, False, False, False)
        ):
            raise ValueError("unsafe identity lookup database role")
        if conn.execute(
            "SELECT EXISTS(SELECT 1 FROM pg_auth_members m JOIN pg_roles r "
            "ON r.oid=m.member WHERE r.rolname=%s) "
            "OR EXISTS(SELECT 1 FROM pg_class c JOIN pg_roles r ON r.oid=c.relowner "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE r.rolname=%s AND n.nspname='public') "
            "OR EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n "
            "ON n.oid=c.relnamespace WHERE n.nspname='public' "
            "AND c.relkind IN ('r','p','v','m','f') "
            "AND has_table_privilege(%s,c.oid,"
            "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN'))",
            (role, role, role),
        ).fetchone() != (False,):
            raise ValueError("identity lookup role has table or inherited authority")
        if conn.execute(
            "SELECT to_regprocedure('public.resolve_external_identity_v2(text,text,text)') "
            "IS NOT NULL"
        ).fetchone() != (True,):
            raise ValueError("source-aware identity resolver migration is missing")
        conn.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role)))
        conn.execute(
            sql.SQL(
                "GRANT EXECUTE ON FUNCTION public.resolve_external_identity(text,text,text) TO {}"
            ).format(sql.Identifier(role))
        )
        conn.execute(
            sql.SQL(
                "GRANT EXECUTE ON FUNCTION "
                "public.resolve_external_identity_v2(text,text,text) TO {}"
            ).format(sql.Identifier(role))
        )
