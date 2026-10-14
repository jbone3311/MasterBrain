"""Forward migration integrity against an isolated synthetic PostgreSQL database."""

from __future__ import annotations

import hashlib
import os
import secrets
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.types.json import Jsonb

from email_brain.migrate import migrate

pytestmark = pytest.mark.postgres
MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"


@pytest.fixture
def scratch_database() -> Iterator[tuple[str, str]]:
    base_dsn = os.environ.get("EMAIL_BRAIN_TEST_ADMIN_DSN")
    if not base_dsn:
        if os.environ.get("CI"):
            pytest.fail("PostgreSQL integration tests are required in CI")
        pytest.skip("No disposable PostgreSQL configured; CI runs this suite")
    if not conninfo_to_dict(base_dsn).get("dbname", "").startswith("email_brain_test"):
        pytest.fail("refusing a database not explicitly named email_brain_test*")

    suffix = uuid4().hex[:12]
    db_name = f"email_brain_test_integrity_{suffix}"
    role_name = f"test_migration_{suffix}"
    password = secrets.token_urlsafe(32)
    admin_dsn = make_conninfo(base_dsn, dbname=db_name)
    owner_dsn = make_conninfo(admin_dsn, user=role_name, password=password)
    with psycopg.connect(base_dsn, autocommit=True) as conn:
        conn.execute(
            sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD {}").format(
                sql.Identifier(role_name), sql.Literal(password)
            )
        )
        try:
            conn.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(db_name), sql.Identifier(role_name)
                )
            )
        except Exception:
            conn.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role_name)))
            raise
    try:
        yield admin_dsn, owner_dsn
    finally:
        with psycopg.connect(base_dsn, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(db_name)))
            conn.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role_name)))


def _migrations_before(tmp_path: Path, limit: int) -> Path:
    earlier = tmp_path / f"migrations_before_{limit}"
    earlier.mkdir()
    for path in MIGRATIONS.glob("[0-9][0-9][0-9][0-9]_*.sql"):
        if int(path.name[:4]) < limit:
            (earlier / path.name).symlink_to(path)
    return earlier


def _migrate_before_repair(dsn: str, tmp_path: Path) -> None:
    earlier = _migrations_before(tmp_path, 29)
    assert len(migrate(dsn, earlier)) == 28


def _run_historical_sql_without_new_preflight(dsn: str, number: int) -> None:
    """Replay the original SQL directly to demonstrate the pre-fix RLS behavior."""
    path = next(MIGRATIONS.glob(f"{number:04d}_*.sql"))
    body = "\n".join(
        line for line in path.read_text().splitlines() if line.strip() not in {"BEGIN;", "COMMIT;"}
    )
    with psycopg.connect(dsn, autocommit=True) as conn, conn.transaction():
        conn.execute(body)


def _seed_message(
    conn: psycopg.Connection[tuple[object, ...]],
    tenant_id: UUID,
    account_id: UUID,
    provider_id: str,
    *,
    deleted: bool = False,
    quarantined: bool = False,
    current_parser: str = "parser-one",
    snapshot_parser: str = "parser-one",
) -> None:
    raw = f"synthetic message {provider_id}".encode()
    digest = hashlib.sha256(raw).hexdigest()
    conn.execute(
        "INSERT INTO raw_objects(tenant_id,account_id,sha256,raw_mime) VALUES (%s,%s,%s,%s)",
        (tenant_id, account_id, digest, raw),
    )
    message_id = conn.execute(
        "INSERT INTO messages(tenant_id,account_id,provider_message_id,provider_version,"
        "subject,sender,recipients,clean_text,raw_sha256,parser_version,received_at,"
        "deleted,quarantined) VALUES (%s,%s,%s,'v1','Synthetic','fixture@example.invalid',"
        "%s,'Synthetic text',%s,%s,%s,%s,%s) RETURNING id",
        (
            tenant_id,
            account_id,
            provider_id,
            Jsonb([]),
            digest,
            current_parser,
            datetime(2026, 9, 20, tzinfo=UTC),
            deleted,
            quarantined,
        ),
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO message_versions(tenant_id,account_id,message_id,raw_sha256,"
        "provider_version,snapshot) VALUES (%s,%s,%s,%s,'v1',%s)",
        (
            tenant_id,
            account_id,
            message_id,
            digest,
            Jsonb({"parser_version": snapshot_parser}),
        ),
    )


def _seed_account(conn: psycopg.Connection[tuple[object, ...]]) -> tuple[UUID, UUID]:
    tenant_id, account_id = uuid4(), uuid4()
    conn.execute("INSERT INTO tenants(id,name) VALUES (%s,'Synthetic')", (tenant_id,))
    conn.execute(
        "INSERT INTO mail_accounts(id,tenant_id,provider,address,secret_ref) "
        "VALUES (%s,%s,'fastmail','fixture@example.invalid','synthetic:none')",
        (account_id, tenant_id),
    )
    return tenant_id, account_id


def test_migrator_rejects_non_bypass_owner_before_schema_ddl(
    scratch_database: tuple[str, str],
) -> None:
    admin_dsn, owner_dsn = scratch_database
    with psycopg.connect(owner_dsn) as conn:
        assert conn.execute(
            "SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user"
        ).fetchone() == (False, False)
    with pytest.raises(ValueError, match="migrations require superuser or BYPASSRLS role"):
        migrate(owner_dsn, MIGRATIONS)
    with psycopg.connect(admin_dsn) as conn:
        assert conn.execute("SELECT to_regclass('public.schema_migrations')").fetchone() == (None,)
        assert conn.execute("SELECT to_regclass('public.tenants')").fetchone() == (None,)


def test_historical_0006_backfill_was_silent_under_forced_rls(
    scratch_database: tuple[str, str],
) -> None:
    admin_dsn, owner_dsn = scratch_database
    for number in range(1, 6):
        _run_historical_sql_without_new_preflight(owner_dsn, number)
    with psycopg.connect(admin_dsn) as conn:
        tenant_id, account_id = _seed_account(conn)
        raw = b"synthetic historical message"
        digest = hashlib.sha256(raw).hexdigest()
        conn.execute(
            "INSERT INTO raw_objects(tenant_id,account_id,sha256,raw_mime) VALUES (%s,%s,%s,%s)",
            (tenant_id, account_id, digest, raw),
        )
        conn.execute(
            "INSERT INTO messages(tenant_id,account_id,provider_message_id,"
            "provider_version,subject,sender,recipients,clean_text,raw_sha256,"
            "parser_version,received_at) VALUES (%s,%s,'pre-0006','v1','Synthetic',"
            "'fixture@example.invalid',%s,'Synthetic text',%s,'parser-one',%s)",
            (
                tenant_id,
                account_id,
                Jsonb([]),
                digest,
                datetime(2026, 9, 20, tzinfo=UTC),
            ),
        )
    _run_historical_sql_without_new_preflight(owner_dsn, 6)
    with psycopg.connect(admin_dsn) as conn:
        assert conn.execute("SELECT count(*) FROM messages").fetchone() == (1,)
        assert conn.execute("SELECT count(*) FROM message_sync_state").fetchone() == (0,)


def test_forward_repair_adds_only_missing_states_and_preserves_existing(
    scratch_database: tuple[str, str], tmp_path: Path
) -> None:
    admin_dsn, _ = scratch_database
    _migrate_before_repair(admin_dsn, tmp_path)
    with psycopg.connect(admin_dsn) as conn:
        tenant_id, account_id = _seed_account(conn)
        other_tenant_id, other_account_id = _seed_account(conn)
        for provider_id, deleted, quarantined in (
            ("missing-ready", False, False),
            ("missing-deleted", True, False),
            ("missing-quarantined", False, True),
            ("already-present", False, False),
        ):
            _seed_message(
                conn,
                tenant_id,
                account_id,
                provider_id,
                deleted=deleted,
                quarantined=quarantined,
            )
        _seed_message(
            conn,
            other_tenant_id,
            other_account_id,
            "missing-ready",
            deleted=True,
        )
        conn.execute(
            "INSERT INTO provider_events(tenant_id,account_id,event_key,kind,"
            "provider_object_id,observed_at) VALUES (%s,%s,'existing-event','synthetic',"
            "'already-present',%s)",
            (tenant_id, account_id, datetime(2026, 9, 20, tzinfo=UTC)),
        )
        conn.execute(
            "INSERT INTO message_sync_state(tenant_id,account_id,provider_id,event_key,"
            "status,updated_at) VALUES (%s,%s,'already-present','existing-event',"
            "'quarantined',%s)",
            (tenant_id, account_id, datetime(2026, 9, 19, tzinfo=UTC)),
        )
        existing_before = conn.execute(
            "SELECT event_key,status,updated_at FROM message_sync_state "
            "WHERE tenant_id=%s AND account_id=%s AND provider_id='already-present'",
            (tenant_id, account_id),
        ).fetchone()

    through_repair = _migrations_before(tmp_path, 30)
    assert migrate(admin_dsn, through_repair) == ["0029_migration_integrity_repair.sql"]
    with psycopg.connect(admin_dsn) as conn:
        rows = conn.execute(
            "SELECT provider_id,event_key,status,updated_at FROM message_sync_state "
            "WHERE tenant_id=%s AND account_id=%s ORDER BY provider_id",
            (tenant_id, account_id),
        ).fetchall()
        other_rows = conn.execute(
            "SELECT provider_id,event_key,status FROM message_sync_state "
            "WHERE tenant_id=%s AND account_id=%s",
            (other_tenant_id, other_account_id),
        ).fetchall()
    by_provider = {row[0]: row[1:] for row in rows}
    assert set(by_provider) == {
        "already-present",
        "missing-ready",
        "missing-deleted",
        "missing-quarantined",
    }
    assert by_provider["already-present"] == existing_before
    assert by_provider["missing-ready"][0:2] == (None, "ready")
    assert by_provider["missing-deleted"][0:2] == (None, "deleted")
    assert by_provider["missing-quarantined"][0:2] == (None, "quarantined")
    assert other_rows == [("missing-ready", None, "deleted")]
    assert migrate(admin_dsn, through_repair) == []


def test_forward_repair_refuses_parser_mismatch_without_partial_write(
    scratch_database: tuple[str, str], tmp_path: Path
) -> None:
    admin_dsn, _ = scratch_database
    _migrate_before_repair(admin_dsn, tmp_path)
    with psycopg.connect(admin_dsn) as conn:
        tenant_id, account_id = _seed_account(conn)
        _seed_message(conn, tenant_id, account_id, "otherwise-repairable")
        _seed_message(
            conn,
            tenant_id,
            account_id,
            "parser-mismatch",
            current_parser="parser-two",
            snapshot_parser="parser-one",
        )
    with pytest.raises(psycopg.errors.RaiseException, match="parser provenance mismatch"):
        migrate(admin_dsn, MIGRATIONS)
    with psycopg.connect(admin_dsn) as conn:
        assert conn.execute("SELECT count(*) FROM message_sync_state").fetchone() == (0,)
        assert conn.execute(
            "SELECT count(*) FROM schema_migrations "
            "WHERE name='0029_migration_integrity_repair.sql'"
        ).fetchone() == (0,)


def test_timeline_index_migration_preserves_populated_event_heap(
    scratch_database: tuple[str, str], tmp_path: Path
) -> None:
    admin_dsn, _ = scratch_database
    earlier = _migrations_before(tmp_path, 54)
    assert len(migrate(admin_dsn, earlier)) == 53
    tenant_id, reviewer_id = uuid4(), uuid4()
    project_id = "project_" + uuid4().hex
    dated_id, undated_id = "event_" + uuid4().hex, "event_" + uuid4().hex
    observed = datetime(2026, 9, 22, tzinfo=UTC)
    with psycopg.connect(admin_dsn) as conn:
        conn.execute("INSERT INTO tenants(id,name) VALUES (%s,'Synthetic timeline')", (tenant_id,))
        conn.execute(
            "INSERT INTO knowledge_projects(tenant_id,id,title,description,state,confidence,"
            "source_quote,observed_at,reviewer_id) "
            "VALUES (%s,%s,'Fictional project','','active',1,'fictional',%s,%s)",
            (tenant_id, project_id, observed, reviewer_id),
        )
        conn.execute(
            "INSERT INTO knowledge_events(tenant_id,id,event_type,title,description,"
            "starts_at,project_id,confidence,source_quote,observed_at,reviewer_id) "
            "VALUES (%s,%s,'decision','Dated event','',%s,%s,1,'fictional',%s,%s)",
            (tenant_id, dated_id, observed, project_id, observed, reviewer_id),
        )
        conn.execute(
            "INSERT INTO knowledge_events(tenant_id,id,event_type,title,description,"
            "confidence,source_quote,observed_at,reviewer_id) "
            "VALUES (%s,%s,'decision','Undated event','',1,'fictional',%s,%s)",
            (tenant_id, undated_id, observed, reviewer_id),
        )
        before = conn.execute(
            "SELECT id,starts_at,project_id,recorded_at,ctid "
            "FROM knowledge_events WHERE tenant_id=%s ORDER BY id", (tenant_id,),
        ).fetchall()
        heap_before = conn.execute(
            "SELECT pg_relation_filenode('knowledge_events'::regclass)"
        ).fetchone()[0]
        assert conn.execute(
            "SELECT to_regclass('knowledge_events_timeline_lookup')"
        ).fetchone() == (None,)

    through_timeline = _migrations_before(tmp_path, 55)
    assert migrate(admin_dsn, through_timeline) == ["0054_knowledge_event_timeline.sql"]
    assert migrate(admin_dsn, through_timeline) == []
    with psycopg.connect(admin_dsn) as conn:
        after = conn.execute(
            "SELECT id,starts_at,project_id,recorded_at,ctid "
            "FROM knowledge_events WHERE tenant_id=%s ORDER BY id", (tenant_id,),
        ).fetchall()
        heap_after = conn.execute(
            "SELECT pg_relation_filenode('knowledge_events'::regclass)"
        ).fetchone()[0]
        indexes = dict(conn.execute(
            "SELECT indexname,indexdef FROM pg_indexes WHERE tablename='knowledge_events' "
            "AND indexname IN ('knowledge_events_timeline_lookup',"
            "'knowledge_events_project_timeline_lookup')"
        ).fetchall())
    assert after == before and heap_after == heap_before
    assert set(indexes) == {
        "knowledge_events_timeline_lookup", "knowledge_events_project_timeline_lookup",
    }
    assert "starts_at IS NOT NULL" in indexes["knowledge_events_timeline_lookup"]
    assert "project_id IS NOT NULL" in indexes["knowledge_events_project_timeline_lookup"]


def test_due_index_migration_preserves_populated_commitment_heap(
    scratch_database: tuple[str, str], tmp_path: Path
) -> None:
    admin_dsn, _ = scratch_database
    earlier = _migrations_before(tmp_path, 55)
    assert len(migrate(admin_dsn, earlier)) == 54
    tenant_id, reviewer_id = uuid4(), uuid4()
    project_id = "project_" + uuid4().hex
    dated_id, undated_id = "commitment_" + uuid4().hex, "commitment_" + uuid4().hex
    observed = datetime(2026, 10, 5, tzinfo=UTC)
    with psycopg.connect(admin_dsn) as conn:
        conn.execute("INSERT INTO tenants(id,name) VALUES (%s,'Synthetic due')", (tenant_id,))
        conn.execute(
            "INSERT INTO knowledge_projects(tenant_id,id,title,description,state,confidence,"
            "source_quote,observed_at,reviewer_id) "
            "VALUES (%s,%s,'Fictional project','','active',1,'fictional',%s,%s)",
            (tenant_id, project_id, observed, reviewer_id),
        )
        conn.execute(
            "INSERT INTO knowledge_commitments(tenant_id,id,description,state,due_at,"
            "project_id,confidence,source_quote,observed_at,reviewer_id) "
            "VALUES (%s,%s,'Dated commitment','open',%s,%s,1,'fictional',%s,%s)",
            (tenant_id, dated_id, observed, project_id, observed, reviewer_id),
        )
        conn.execute(
            "INSERT INTO knowledge_commitments(tenant_id,id,description,state,"
            "confidence,source_quote,observed_at,reviewer_id) "
            "VALUES (%s,%s,'Undated commitment','open',1,'fictional',%s,%s)",
            (tenant_id, undated_id, observed, reviewer_id),
        )
        before = conn.execute(
            "SELECT id,due_at,project_id,recorded_at,ctid FROM knowledge_commitments "
            "WHERE tenant_id=%s ORDER BY id", (tenant_id,),
        ).fetchall()
        heap_before = conn.execute(
            "SELECT pg_relation_filenode('knowledge_commitments'::regclass)"
        ).fetchone()[0]
        assert conn.execute(
            "SELECT to_regclass('knowledge_commitments_due_lookup')"
        ).fetchone() == (None,)

    through_due = _migrations_before(tmp_path, 56)
    assert migrate(admin_dsn, through_due) == ["0055_knowledge_commitment_due.sql"]
    assert migrate(admin_dsn, through_due) == []
    with psycopg.connect(admin_dsn) as conn:
        after = conn.execute(
            "SELECT id,due_at,project_id,recorded_at,ctid FROM knowledge_commitments "
            "WHERE tenant_id=%s ORDER BY id", (tenant_id,),
        ).fetchall()
        heap_after = conn.execute(
            "SELECT pg_relation_filenode('knowledge_commitments'::regclass)"
        ).fetchone()[0]
        indexes = dict(conn.execute(
            "SELECT indexname,indexdef FROM pg_indexes WHERE tablename='knowledge_commitments' "
            "AND indexname IN ('knowledge_commitments_due_lookup',"
            "'knowledge_commitments_project_due_lookup')"
        ).fetchall())
    assert after == before and heap_after == heap_before
    assert set(indexes) == {
        "knowledge_commitments_due_lookup", "knowledge_commitments_project_due_lookup",
    }
    assert "due_at IS NOT NULL" in indexes["knowledge_commitments_due_lookup"]
    assert "project_id IS NOT NULL" in indexes["knowledge_commitments_project_due_lookup"]


def test_project_dossier_indexes_preserve_populated_assertion_heaps(
    scratch_database: tuple[str, str], tmp_path: Path
) -> None:
    admin_dsn, _ = scratch_database
    earlier = _migrations_before(tmp_path, 56)
    assert len(migrate(admin_dsn, earlier)) == 55
    tenant_id, reviewer_id = uuid4(), uuid4()
    project_id = "project_" + uuid4().hex
    event_id = "event_" + uuid4().hex
    commitment_id = "commitment_" + uuid4().hex
    observed = datetime(2026, 10, 5, tzinfo=UTC)
    with psycopg.connect(admin_dsn) as conn:
        conn.execute("INSERT INTO tenants(id,name) VALUES (%s,'Synthetic dossier')", (tenant_id,))
        conn.execute(
            "INSERT INTO knowledge_projects(tenant_id,id,title,description,state,confidence,"
            "source_quote,observed_at,reviewer_id) "
            "VALUES (%s,%s,'Fictional dossier','','active',1,'fictional',%s,%s)",
            (tenant_id, project_id, observed, reviewer_id),
        )
        conn.execute(
            "INSERT INTO knowledge_events(tenant_id,id,event_type,title,description,"
            "project_id,confidence,source_quote,observed_at,reviewer_id) "
            "VALUES (%s,%s,'review','Fictional undated','',%s,1,'fictional',%s,%s)",
            (tenant_id, event_id, project_id, observed, reviewer_id),
        )
        conn.execute(
            "INSERT INTO knowledge_commitments(tenant_id,id,description,state,project_id,"
            "confidence,source_quote,observed_at,reviewer_id) "
            "VALUES (%s,%s,'Fictional undated','open',%s,1,'fictional',%s,%s)",
            (tenant_id, commitment_id, project_id, observed, reviewer_id),
        )
        before = {
            table: conn.execute(
                f"SELECT ctid,recorded_at FROM {table} WHERE tenant_id=%s AND id=%s",
                (tenant_id, object_id),
            ).fetchone()
            for table, object_id in (
                ("knowledge_events", event_id),
                ("knowledge_commitments", commitment_id),
            )
        }
        heaps = {
            table: conn.execute(
                "SELECT pg_relation_filenode(%s::regclass)", (table,),
            ).fetchone()[0]
            for table in before
        }
    assert migrate(admin_dsn, MIGRATIONS) == [
        "0056_knowledge_project_dossier.sql",
        "0057_private_statement_proposals.sql",
        "0058_fastmail_scoped_lease.sql",
        "0059_reviewed_project_aliases.sql",
    ]
    assert migrate(admin_dsn, MIGRATIONS) == []
    with psycopg.connect(admin_dsn) as conn:
        for table, object_id in (
            ("knowledge_events", event_id),
            ("knowledge_commitments", commitment_id),
        ):
            assert conn.execute(
                f"SELECT ctid,recorded_at FROM {table} WHERE tenant_id=%s AND id=%s",
                (tenant_id, object_id),
            ).fetchone() == before[table]
            assert conn.execute(
                "SELECT pg_relation_filenode(%s::regclass)", (table,),
            ).fetchone()[0] == heaps[table]
            index = dict(conn.execute(
                "SELECT indexname,indexdef FROM pg_indexes WHERE tablename=%s "
                "AND indexname=%s",
                (table, table + "_project_recorded_lookup"),
            ).fetchall())
            assert len(index) == 1
            definition = next(iter(index.values()))
            assert "project_id IS NOT NULL" in definition
            assert "recorded_at DESC" in definition
