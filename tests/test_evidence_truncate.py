"""PostgreSQL regression for ADR-092's protected-record TRUNCATE boundary.

All data and roles live in a disposable email_brain_test* database. No source or
production content is used, and the historical destructive proof is rolled back.
"""

from __future__ import annotations

import hashlib
import os
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.types.json import Jsonb

from email_brain.migrate import grant_runtime, migrate

pytestmark = pytest.mark.postgres
MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"
SPECIAL = {"recovery_jobs", "document_jobs", "external_identities"}
TRUNCATE_MIGRATION = "0030_protected_record_truncate_guards.sql"
REJECTION = "protected record; retention requires a separately authorized maintenance path"


@contextmanager
def _scratch_database() -> Iterator[tuple[str, str]]:
    base_dsn = os.environ.get("EMAIL_BRAIN_TEST_ADMIN_DSN")
    if not base_dsn:
        if os.environ.get("CI"):
            pytest.fail("PostgreSQL integration tests are required in CI")
        pytest.skip("No disposable PostgreSQL configured; CI runs this suite")
    if not conninfo_to_dict(base_dsn).get("dbname", "").startswith("email_brain_test"):
        pytest.fail("refusing a database not explicitly named email_brain_test*")

    suffix = uuid4().hex[:12]
    db_name = f"email_brain_test_truncate_{suffix}"
    role_name = f"test_truncate_{suffix}"
    password = secrets.token_urlsafe(32)
    admin_dsn = make_conninfo(base_dsn, dbname=db_name)
    runtime_dsn = make_conninfo(admin_dsn, user=role_name, password=password)
    with psycopg.connect(base_dsn, autocommit=True) as conn:
        conn.execute(
            sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD {}").format(
                sql.Identifier(role_name), sql.Literal(password)
            )
        )
        try:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
        except Exception:
            conn.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role_name)))
            raise
    try:
        yield admin_dsn, runtime_dsn
    finally:
        with psycopg.connect(base_dsn, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(db_name)))
            conn.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role_name)))


def _migrate_before_0030(dsn: str, tmp_path: Path) -> None:
    earlier = tmp_path / "earlier_migrations"
    earlier.mkdir()
    for path in MIGRATIONS.glob("[0-9][0-9][0-9][0-9]_*.sql"):
        if int(path.name[:4]) < 30:
            (earlier / path.name).symlink_to(path)
    assert len(migrate(dsn, earlier)) == 29


def _seed_records(dsn: str) -> dict[str, UUID | int]:
    tenant_id, actor_id, account_id = uuid4(), uuid4(), uuid4()
    raw = b"synthetic truncation-guard message"
    digest = hashlib.sha256(raw).hexdigest()
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "INSERT INTO tenants(id,name) VALUES (%s,'Synthetic guard test')", (tenant_id,)
        )
        conn.execute(
            "INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES (%s,%s,'owner')",
            (tenant_id, actor_id),
        )
        conn.execute(
            "INSERT INTO mail_accounts(id,tenant_id,provider,address,secret_ref) "
            "VALUES (%s,%s,'fastmail','guard@example.invalid','synthetic:none')",
            (account_id, tenant_id),
        )
        conn.execute(
            "INSERT INTO raw_objects(tenant_id,account_id,sha256,raw_mime) VALUES (%s,%s,%s,%s)",
            (tenant_id, account_id, digest, raw),
        )
        conn.execute(
            "INSERT INTO provider_events(tenant_id,account_id,event_key,kind,provider_object_id,"
            "observed_at) VALUES (%s,%s,'guard-event','synthetic','guard-message',%s)",
            (tenant_id, account_id, datetime(2026, 9, 20, tzinfo=UTC)),
        )
        message_id = conn.execute(
            "INSERT INTO messages(tenant_id,account_id,provider_message_id,provider_version,"
            "subject,sender,recipients,clean_text,raw_sha256,parser_version,received_at) "
            "VALUES (%s,%s,'guard-message','v1','Synthetic','fixture@example.invalid',"
            "%s,'Synthetic text',%s,'parser-one',%s) RETURNING id",
            (tenant_id, account_id, Jsonb([]), digest, datetime(2026, 9, 20, tzinfo=UTC)),
        ).fetchone()[0]
        version_id = conn.execute(
            "INSERT INTO message_versions(tenant_id,account_id,message_id,raw_sha256,"
            "provider_version,snapshot) VALUES (%s,%s,%s,%s,'v1',%s) RETURNING id",
            (tenant_id, account_id, message_id, digest, Jsonb({"parser_version": "parser-one"})),
        ).fetchone()[0]
        receipt_id = conn.execute(
            "INSERT INTO quarantine_receipts(tenant_id,account_id,event_key,provider_id,"
            "raw_sha256,reason,parser_version) VALUES (%s,%s,'guard-event','guard-message',"
            "%s,'mime_rejected','parser-one') RETURNING id",
            (tenant_id, account_id, digest),
        ).fetchone()[0]
        attachment_id = conn.execute(
            "INSERT INTO attachment_receipts(tenant_id,account_id,evidence_id,part_id,"
            "original_filename,safe_filename,media_type,sha256,byte_size,status,reason) "
            "VALUES (%s,%s,%s,'1','fixture.txt','fixture.txt','text/plain',%s,0,'deferred',"
            "'synthetic') RETURNING id",
            (tenant_id, account_id, version_id, digest),
        ).fetchone()[0]
        recovery_id = conn.execute(
            "INSERT INTO recovery_jobs(tenant_id,account_id,receipt_id,actor_id,"
            "idempotency_key,parser_version) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
            (tenant_id, account_id, receipt_id, actor_id, uuid4(), "sandbox-mime-v1-" + "a" * 64),
        ).fetchone()[0]
        document_id = conn.execute(
            "INSERT INTO document_jobs(tenant_id,account_id,receipt_id,source_event_key,"
            "actor_id,idempotency_key,processor_version,policy_version) "
            "VALUES (%s,%s,%s,'guard-event',%s,%s,%s,'synthetic-unscanned-pdf-v1') "
            "RETURNING id",
            (tenant_id, account_id, attachment_id, actor_id, uuid4(), "sandbox-pdf-v1-" + "a" * 64),
        ).fetchone()[0]
        identity_id = uuid4()
        conn.execute(
            "INSERT INTO external_identities(id,tenant_id,actor_id,issuer,subject,client_id,"
            "scopes,client_kind) VALUES (%s,%s,%s,'https://fixture.invalid/','guard-subject',"
            "'guard-client',ARRAY['email.search'],'human')",
            (identity_id, tenant_id, actor_id),
        )
        conn.execute(
            "INSERT INTO audit_events(tenant_id,actor_id,request_id,event_type,resource_type,"
            "resource_id,outcome) VALUES (%s,%s,%s,'guard.seed','synthetic','guard','ok')",
            (tenant_id, actor_id, uuid4()),
        )
        audit_count = conn.execute(
            "SELECT count(*) FROM audit_events WHERE tenant_id=%s", (tenant_id,)
        ).fetchone()[0]
    return {
        "tenant_id": tenant_id,
        "actor_id": actor_id,
        "account_id": account_id,
        "recovery_id": recovery_id,
        "document_id": document_id,
        "identity_id": identity_id,
        "audit_count": audit_count,
    }


def _guarded_tables(conn: psycopg.Connection[tuple[object, ...]]) -> set[str]:
    return {
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT c.relname FROM pg_trigger t "
            "JOIN pg_class c ON c.oid=t.tgrelid "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND NOT t.tgisinternal "
            "AND t.tgfoid='public.deny_evidence_mutation()'::regprocedure "
            "AND (t.tgtype & 1)=1 AND (t.tgtype & 2)=2 "
            "AND (t.tgtype & 8)=8 AND (t.tgtype & 16)=16"
        )
    }


def _record_counts(dsn: str, tenant_id: UUID) -> dict[str, int]:
    tables = (
        "tenants",
        "tenant_memberships",
        "mail_accounts",
        "raw_objects",
        "messages",
        "message_versions",
        "provider_events",
        "quarantine_receipts",
        "attachment_receipts",
        "audit_events",
        "recovery_jobs",
        "document_jobs",
        "external_identities",
    )
    with psycopg.connect(dsn) as conn:
        return {
            table: conn.execute(
                sql.SQL("SELECT count(*) FROM {} WHERE {}=%s").format(
                    sql.Identifier(table),
                    sql.Identifier("id" if table == "tenants" else "tenant_id"),
                ),
                (tenant_id,),
            ).fetchone()[0]
            for table in tables
        }


@pytest.fixture(scope="module")
def pre_0030(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[tuple[str, dict[str, UUID | int]]]:
    with _scratch_database() as (dsn, _):
        _migrate_before_0030(dsn, tmp_path_factory.mktemp("truncate_pre"))
        yield dsn, _seed_records(dsn)


@pytest.fixture(scope="module")
def protected_database(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[tuple[str, str, dict[str, UUID | int]]]:
    with _scratch_database() as (admin_dsn, runtime_dsn):
        _migrate_before_0030(admin_dsn, tmp_path_factory.mktemp("truncate_post"))
        seeded = _seed_records(admin_dsn)
        tenant_id = seeded["tenant_id"]
        assert isinstance(tenant_id, UUID)
        before = _record_counts(admin_dsn, tenant_id)
        assert migrate(admin_dsn, MIGRATIONS) == [
            TRUNCATE_MIGRATION,
            "0031_fileos_policy_identity.sql",
            "0032_fileos_root_binding.sql",
            "0033_archive_ledger_parent_integrity.sql",
            "0034_identity_admin_enrollment.sql",
            "0035_identity_resolver.sql",
            "0036_current_archive_image_search.sql",
            "0037_tenant_login_fence.sql",
            "0038_fileos_transition_review_packets.sql",
            "0039_fileos_v2_staged_inventory.sql",
            "0040_fileos_v2_transition_approvals.sql",
            "0041_fileos_v2_baseline_verification.sql",
            "0042_fileos_v2_prepared_evidence.sql",
            "0043_fileos_run_ledger_linear_validation.sql",
            "0044_fileos_v2_baseline_authorizations.sql",
            "0045_fileos_v2_baseline_completion.sql",
            "0046_fileos_v2_document_publication.sql",
            "0047_fileos_v2_shared_index_generation.sql",
            "0048_fileos_v2_readiness_indexed_check.sql",
            "0049_oidc_brain_source_grants.sql",
            "0050_oidc_brain_read_status.sql",
            "0051_oidc_knowledge_read_grants.sql",
            "0052_held_source_quarantine.sql",
            "0053_knowledge_unsuperseded_lookup.sql",
            "0054_knowledge_event_timeline.sql",
        ]
        assert _record_counts(admin_dsn, tenant_id) == before
        with psycopg.connect(admin_dsn) as conn:
            grant_runtime(conn, conninfo_to_dict(runtime_dsn)["user"])
        yield admin_dsn, runtime_dsn, seeded


def test_historical_owner_gap_reproduced_only_inside_rollback(
    pre_0030: tuple[str, dict[str, UUID | int]],
) -> None:
    dsn, seeded = pre_0030
    tenant_id = seeded["tenant_id"]
    assert isinstance(tenant_id, UUID)
    before = _record_counts(dsn, tenant_id)
    assert before["audit_events"] >= 2
    with psycopg.connect(dsn) as conn:
        conn.execute("TRUNCATE audit_events")
        assert conn.execute("SELECT count(*) FROM audit_events").fetchone() == (0,)
        conn.rollback()
    assert _record_counts(dsn, tenant_id) == before


def test_catalog_has_exact_67_plus_three_statement_guards(
    protected_database: tuple[str, str, dict[str, UUID | int]],
) -> None:
    admin_dsn, _, _ = protected_database
    with psycopg.connect(admin_dsn) as conn:
        row_guarded = _guarded_tables(conn)
        assert len(row_guarded) == 67
        assert not (row_guarded & SPECIAL)
        rows = conn.execute(
            "SELECT c.relname,t.tgname,t.tgenabled,t.tgisinternal,t.tgtype,"
            "t.tgfoid='public.deny_protected_truncate()'::regprocedure "
            "FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND (t.tgtype & 32)=32"
        ).fetchall()
    assert len(rows) == 70
    assert {row[0] for row in rows} == row_guarded | SPECIAL
    assert all(
        name == "protected_no_truncate"
        and enabled in ("O", "A")
        and not internal
        and trigger_type == 34  # BEFORE TRUNCATE FOR EACH STATEMENT
        and correct_function
        for _, name, enabled, internal, trigger_type, correct_function in rows
    )


@pytest.mark.parametrize("table", sorted(SPECIAL | {"audit_events"}))
def test_direct_truncate_rejected_without_row_loss(
    protected_database: tuple[str, str, dict[str, UUID | int]], table: str
) -> None:
    admin_dsn, _, seeded = protected_database
    tenant_id = seeded["tenant_id"]
    assert isinstance(tenant_id, UUID)
    before = _record_counts(admin_dsn, tenant_id)
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        if table in {"document_jobs", "external_identities"}:
            # Their bridge/source-grant FKs are checked before statement triggers.
            # CASCADE is covered separately and must reach the rejecting guard.
            with pytest.raises(psycopg.errors.FeatureNotSupported):
                conn.execute(sql.SQL("TRUNCATE {}").format(sql.Identifier(table)))
        else:
            with pytest.raises(psycopg.errors.RaiseException, match=REJECTION):
                conn.execute(sql.SQL("TRUNCATE {}").format(sql.Identifier(table)))
    assert _record_counts(admin_dsn, tenant_id) == before


def test_every_protected_table_refuses_cascaded_truncate(
    protected_database: tuple[str, str, dict[str, UUID | int]],
) -> None:
    admin_dsn, _, seeded = protected_database
    tenant_id = seeded["tenant_id"]
    assert isinstance(tenant_id, UUID)
    before = _record_counts(admin_dsn, tenant_id)
    with psycopg.connect(admin_dsn) as conn:
        targets = sorted(_guarded_tables(conn) | SPECIAL)
    assert len(targets) == 70
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        for table in targets:
            with pytest.raises(psycopg.errors.RaiseException, match=REJECTION):
                conn.execute(sql.SQL("TRUNCATE {} CASCADE").format(sql.Identifier(table)))
    assert _record_counts(admin_dsn, tenant_id) == before


@pytest.mark.parametrize("parent", ["tenants", "tenant_memberships", "mail_accounts"])
def test_parent_cascade_is_atomic(
    protected_database: tuple[str, str, dict[str, UUID | int]], parent: str
) -> None:
    admin_dsn, _, seeded = protected_database
    tenant_id = seeded["tenant_id"]
    assert isinstance(tenant_id, UUID)
    before = _record_counts(admin_dsn, tenant_id)
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        with pytest.raises(psycopg.errors.RaiseException, match=REJECTION):
            conn.execute(sql.SQL("TRUNCATE {} CASCADE").format(sql.Identifier(parent)))
    assert _record_counts(admin_dsn, tenant_id) == before


def test_runtime_role_has_no_truncate_privilege(
    protected_database: tuple[str, str, dict[str, UUID | int]],
) -> None:
    admin_dsn, runtime_dsn, seeded = protected_database
    tenant_id = seeded["tenant_id"]
    assert isinstance(tenant_id, UUID)
    before = _record_counts(admin_dsn, tenant_id)
    with psycopg.connect(runtime_dsn, autocommit=True) as conn:
        privilege = conn.execute(
            "SELECT has_table_privilege(current_user,'audit_events','TRUNCATE')"
        ).fetchone()
        assert privilege == (False,)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("TRUNCATE audit_events")
    assert _record_counts(admin_dsn, tenant_id) == before


def test_row_guards_and_legitimate_job_identity_paths_unchanged(
    protected_database: tuple[str, str, dict[str, UUID | int]],
) -> None:
    admin_dsn, _, seeded = protected_database
    tenant_id = seeded["tenant_id"]
    assert isinstance(tenant_id, UUID)
    before = _record_counts(admin_dsn, tenant_id)
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        for statement in ("UPDATE audit_events SET outcome='changed'", "DELETE FROM audit_events"):
            with pytest.raises(psycopg.errors.RaiseException, match="append-only record"):
                conn.execute(statement)
    with psycopg.connect(admin_dsn) as conn:
        for table, key in (("recovery_jobs", "recovery_id"), ("document_jobs", "document_id")):
            assert conn.execute(
                sql.SQL(
                    "UPDATE {} SET status='cancelled',outcome='cancelled',"
                    "completed_at=statement_timestamp() WHERE id=%s RETURNING status"
                ).format(sql.Identifier(table)),
                (seeded[key],),
            ).fetchone() == ("cancelled",)
        identity_before = conn.execute(
            "SELECT revision FROM external_identities WHERE id=%s", (seeded["identity_id"],)
        ).fetchone()[0]
        audit_before = conn.execute("SELECT count(*) FROM audit_events").fetchone()[0]
        assert conn.execute(
            "UPDATE external_identities SET active=false WHERE id=%s RETURNING revision",
            (seeded["identity_id"],),
        ).fetchone() == (identity_before + 1,)
        assert conn.execute("SELECT count(*) FROM audit_events").fetchone() == (audit_before + 1,)
        conn.rollback()  # Keep module-scoped synthetic fixture unchanged.
    assert _record_counts(admin_dsn, tenant_id) == before


def test_migration_replay_is_noop(
    protected_database: tuple[str, str, dict[str, UUID | int]],
) -> None:
    admin_dsn, _, seeded = protected_database
    tenant_id = seeded["tenant_id"]
    assert isinstance(tenant_id, UUID)
    before = _record_counts(admin_dsn, tenant_id)
    assert migrate(admin_dsn, MIGRATIONS) == []
    assert _record_counts(admin_dsn, tenant_id) == before
    with psycopg.connect(admin_dsn) as conn:
        assert conn.execute(
            "SELECT count(*) FROM schema_migrations WHERE name=%s", (TRUNCATE_MIGRATION,)
        ).fetchone() == (1,)
