"""Real PostgreSQL tests. Only run against a disposable database named email_brain_test*.

CI supplies the database; no real credentials/accounts/mailboxes are involved.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import random
import secrets
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from typing import Any
from unittest.mock import Mock
from uuid import UUID, uuid4

import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from email_brain.api import create_app
from email_brain.auth import Credential, TokenRegistry
from email_brain.connectors.fastmail import MAIL, FastmailReadClient
from email_brain.domain.models import TenantContext
from email_brain.migrate import grant_identity_lookup, grant_runtime, grant_tenant_runtime, migrate
from email_brain.oidc import OIDCAuthenticator, VerifiedToken
from email_brain.schemas import FeaturePayload, ProposalRequest, ReviewRequest, SearchRequest
from email_brain.store import AccessDenied, Conflict, IngestItem, InventoryError, NotFound, Store
from email_brain.sync import Checkpoint, ReadWorker
from email_brain.sync_store import SyncStore
from email_brain.synthetic import fake_email
from email_brain.synthetic_formats import docx_bytes, pdf_bytes, xlsx_bytes
from masterbrain import archive_member_controller as archive_controller
from masterbrain.datacore import fileos_donor_transition as transition_module
from masterbrain.datacore.archive_contract import ArchiveResult, ArchiveSkip, source_for
from masterbrain.datacore.archive_member_contract import decode_result as decode_member_result
from masterbrain.datacore.archive_member_contract import encode_request as encode_member_request
from masterbrain.datacore.archive_member_text import (
    archive_member_version_id,
    publish_extracted_archive_member_text,
)
from masterbrain.datacore.archive_member_worker import process_request as read_archive_member
from masterbrain.datacore.archive_worker import inventory_archive
from masterbrain.datacore.extraction import ExtractionResult, ExtractionStatus, FileOSAdapter
from masterbrain.datacore.fileos import snapshot_tree
from masterbrain.datacore.fileos_donor_transition import (
    build_fileos_transition_review_packet,
    preview_fileos_completed_donor_transition,
    record_fileos_transition_review,
)
from masterbrain.datacore.image_ocr_contract import CONTRACT as IMAGE_OCR_CONTRACT
from masterbrain.datacore.image_ocr_contract import ImageOcrResult
from masterbrain.datacore.image_ocr_contract import source_for as image_source_for
from masterbrain.datacore.persistence import (
    ArchiveMemberTargetRecord,
    DataCoreStore,
    fileos_inventory_policy_sha256,
)
from masterbrain.email_bridge_controller import (
    EmailBridgeBatchItem,
    EmailPartBridgeBatchItem,
    email_bridge_batch_sha256,
    email_part_bridge_batch_sha256,
    run_email_bridge_batch_controller,
    run_email_bridge_controller,
    run_email_part_bridge_batch_controller,
)
from masterbrain.knowledge import KnowledgeCore
from masterbrain.knowledge_schema import (
    ClaimWrite,
    CommitmentWrite,
    CorrectionWrite,
    EntityWrite,
    EventWrite,
    ProjectWrite,
    RelationshipWrite,
)

pytestmark = pytest.mark.postgres


@pytest.fixture(scope="module")
def database() -> tuple[Store, str]:
    dsn = os.environ.get("EMAIL_BRAIN_TEST_ADMIN_DSN")
    if not dsn:
        if os.environ.get("CI"):
            pytest.fail("PostgreSQL integration tests are required in CI")
        pytest.skip("No disposable PostgreSQL configured; CI runs this suite")
    assert dsn is not None
    config = conninfo_to_dict(dsn)
    if not config.get("dbname", "").startswith("email_brain_test"):
        pytest.fail("refusing a database not explicitly named email_brain_test*")
    root = Path(__file__).resolve().parents[1]
    migrate(dsn, root / "migrations")
    assert migrate(dsn, root / "migrations") == []
    role = "test_runtime_" + uuid4().hex[:12]
    password = secrets.token_urlsafe(32)
    with psycopg.connect(dsn) as conn:
        conn.execute(
            sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD {}").format(
                sql.Identifier(role), sql.Literal(password)
            )
        )
        grant_runtime(conn, role)
    return Store(make_conninfo(dsn, user=role, password=password)), dsn


@pytest.fixture
def tenant(database: tuple[Store, str]) -> tuple[TenantContext, UUID]:
    _, admin = database
    tenant_id, actor_id, account_id = uuid4(), uuid4(), uuid4()
    with psycopg.connect(admin) as conn:
        conn.execute("INSERT INTO tenants(id,name) VALUES (%s,'Synthetic test')", (tenant_id,))
        conn.execute(
            "INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES (%s,%s,'owner')",
            (tenant_id, actor_id),
        )
        conn.execute(
            "INSERT INTO mail_accounts(id,tenant_id,provider,address,secret_ref) "
            "VALUES (%s,%s,'fastmail','synthetic@example.invalid','synthetic:none')",
            (account_id, tenant_id),
        )
    return TenantContext(
        tenant_id,
        actor_id,
        frozenset(
            {
                "email.ingest",
                "email.search",
                "email.evidence.read",
                "email.proposal.create",
                "email.proposal.read",
                "email.review",
            }
        ),
        uuid4(),
    ), account_id


def test_tenant_login_fence_contains_forged_sql_context(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID]
) -> None:
    """A stolen single-tenant DSN cannot turn caller-settable GUCs into another tenant."""
    _, admin = database
    ctx, own_account = tenant
    other_tenant, other_actor = uuid4(), uuid4()
    other_account, own_binding, other_binding = uuid4(), uuid4(), uuid4()
    issuer = "fence-issuer-" + uuid4().hex
    role = "test_tenant_runtime_" + uuid4().hex[:12]
    auxiliary_role = "test_tenant_aux_" + uuid4().hex[:12]
    password = secrets.token_urlsafe(32)
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO tenants(id,name) VALUES (%s,'Other fictional tenant')",
            (other_tenant,),
        )
        conn.execute(
            "INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES (%s,%s,'owner')",
            (other_tenant, other_actor),
        )
        conn.execute(
            "INSERT INTO brain_sources(tenant_id,id,kind,display_name) "
            "VALUES (%s,'fence_other','email','Other fictional source')",
            (other_tenant,),
        )
        conn.execute(
            "INSERT INTO mail_accounts(id,tenant_id,provider,address,secret_ref) "
            "VALUES (%s,%s,'fastmail','other@example.invalid','synthetic:none')",
            (other_account, other_tenant),
        )
        for binding_id, tenant_id, actor_id, subject in (
            (own_binding, ctx.tenant_id, ctx.actor_id, "fence-own"),
            (other_binding, other_tenant, other_actor, "fence-other"),
        ):
            conn.execute(
                "INSERT INTO external_identities(id,tenant_id,actor_id,issuer,subject,"
                "client_id,scopes,client_kind) VALUES (%s,%s,%s,%s,%s,"
                "'fence-client',ARRAY['email.search'],'human')",
                (binding_id, tenant_id, actor_id, issuer, subject),
            )
        conn.execute(
            sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD {}").format(
                sql.Identifier(role), sql.Literal(password)
            )
        )
        grant_tenant_runtime(conn, role, ctx.tenant_id)
        conn.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(auxiliary_role)))
        conn.execute(
            sql.SQL("GRANT {} TO {} WITH ADMIN FALSE, INHERIT FALSE, SET TRUE").format(
                sql.Identifier(auxiliary_role), sql.Identifier(role)
            )
        )
        assert conn.execute(
            "SELECT tenant_id FROM masterbrain_tenant_login_bindings WHERE role_name=%s",
            (role,),
        ).fetchone() == (ctx.tenant_id,)
        assert conn.execute(
            "SELECT count(*) FROM audit_events WHERE event_type='tenant_login.insert' "
            "AND resource_type='database_role' AND resource_id=%s",
            (role,),
        ).fetchone() == (1,)
        with pytest.raises(psycopg.errors.RaiseException), conn.transaction():
            conn.execute(
                "UPDATE masterbrain_tenant_login_bindings SET tenant_id=%s WHERE role_name=%s",
                (other_tenant, role),
            )
        assert (
            conn.execute(
                "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname='public' AND c.relkind='r' AND "
                "(c.relname='tenants' OR EXISTS (SELECT 1 FROM pg_attribute a "
                "WHERE a.attrelid=c.oid AND a.attname='tenant_id' AND a.attnum>0)) "
                "AND (NOT c.relrowsecurity OR NOT c.relforcerowsecurity "
                "OR NOT EXISTS (SELECT 1 FROM pg_policy p "
                "WHERE p.polrelid=c.oid AND p.polname='tenant_login_fence' "
                "AND NOT p.polpermissive))"
            ).fetchall()
            == []
        )
        with pytest.raises(ValueError, match="already bound"):
            grant_tenant_runtime(conn, role, other_tenant)
    runtime_dsn = make_conninfo(admin, user=role, password=password)
    with Store(runtime_dsn).transaction(ctx) as conn:
        assert conn.execute("SELECT id FROM tenants").fetchall() == [{"id": ctx.tenant_id}]
        assert conn.execute(
            "SELECT public.masterbrain_tenant_login_allows(%s) AS allowed",
            (other_tenant,),
        ).fetchone() == {"allowed": False}
        conn.execute(
            "INSERT INTO audit_events(tenant_id,actor_id,request_id,event_type,"
            "resource_type,outcome) VALUES (%s,%s,%s,'allowed','tenant','ok')",
            (ctx.tenant_id, ctx.actor_id, uuid4()),
        )
        conn.execute(
            "INSERT INTO brain_sources(tenant_id,id,kind,display_name) "
            "VALUES (%s,'fence_own','email','Own fictional source')",
            (ctx.tenant_id,),
        )
    with psycopg.connect(runtime_dsn) as conn:
        conn.execute("SELECT set_config('email_brain.tenant_id', %s, true)", (str(other_tenant),))
        conn.execute("SELECT set_config('email_brain.actor_id', %s, true)", (str(other_actor),))
        for setting, forged_value in (
            ("email_brain.auth_issuer", "forged-issuer"),
            ("email_brain.auth_subject", "forged-subject"),
            ("email_brain.auth_client", "forged-client"),
        ):
            conn.execute("SELECT set_config(%s,%s,true)", (setting, forged_value))
        assert (
            conn.execute(
                "SELECT id FROM public.resolve_external_identity(%s,'fence-other','fence-client')",
                (issuer,),
            ).fetchall()
            == []
        )
        assert conn.execute(
            "SELECT id FROM public.resolve_external_identity(%s,'fence-own','fence-client')",
            (issuer,),
        ).fetchone() == (own_binding,)
        assert conn.execute(
            "SELECT public.lock_recovery_owners(%s,%s,%s)",
            (other_account, other_actor, other_actor),
        ).fetchone() == (False,)
        assert conn.execute("SELECT id FROM tenants WHERE id=%s", (other_tenant,)).fetchall() == []
        assert (
            conn.execute(
                "SELECT tenant_id,user_id FROM tenant_memberships WHERE tenant_id=%s",
                (other_tenant,),
            ).fetchall()
            == []
        )
        assert (
            conn.execute(
                "SELECT id FROM brain_sources WHERE tenant_id=%s", (other_tenant,)
            ).fetchall()
            == []
        )
        assert (
            conn.execute(
                "UPDATE brain_sources SET status='paused' WHERE tenant_id=%s AND id='fence_other'",
                (other_tenant,),
            ).rowcount
            == 0
        )
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute(
                "INSERT INTO brain_sources(tenant_id,id,kind,display_name) "
                "VALUES (%s,'fence_forged','email','Forged source')",
                (other_tenant,),
            )
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute(
                "INSERT INTO audit_events(tenant_id,actor_id,request_id,event_type,"
                "resource_type,outcome) VALUES (%s,%s,%s,'forged','tenant','ok')",
                (other_tenant, other_actor, uuid4()),
            )
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute("SELECT * FROM masterbrain_tenant_login_bindings")
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute("SET ROLE masterbrain_identity_admin")
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute("SET SESSION AUTHORIZATION masterbrain_identity_admin")
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute("SET ROLE masterbrain_tenant_runtime")
        conn.execute("SELECT set_config('email_brain.tenant_id', %s, true)", (str(ctx.tenant_id),))
        assert conn.execute(
            "SELECT public.lock_recovery_owners(%s,%s,%s)",
            (own_account, ctx.actor_id, ctx.actor_id),
        ).fetchone() == (True,)
        conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(auxiliary_role)))
        assert conn.execute("SELECT session_user <> current_user").fetchone() == (True,)
        assert conn.execute(
            "SELECT public.masterbrain_tenant_login_allows(%s)", (other_tenant,)
        ).fetchone() == (False,)
        conn.execute("RESET ROLE")
    # Even an administrator accidentally removing a mapping leaves a marker member
    # fail-closed instead of silently reverting to the shared-login behavior.
    with psycopg.connect(admin) as conn:
        conn.execute("DELETE FROM masterbrain_tenant_login_bindings WHERE role_name=%s", (role,))
        assert conn.execute(
            "SELECT count(*) FROM audit_events WHERE event_type='tenant_login.delete' "
            "AND resource_type='database_role' AND resource_id=%s",
            (role,),
        ).fetchone() == (1,)
        with pytest.raises(ValueError, match="cannot be reused"):
            grant_tenant_runtime(conn, role, other_tenant)
    with psycopg.connect(runtime_dsn) as conn:
        conn.execute("SELECT set_config('email_brain.tenant_id', %s, true)", (str(ctx.tenant_id),))
        assert conn.execute("SELECT id FROM tenants WHERE id=%s", (ctx.tenant_id,)).fetchall() == []


def test_tenant_database_routing_two_tenant_api_and_fail_closed_routes(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID]
) -> None:
    """One exact lookup credential and two bound data logins back real API searches."""
    shared, admin = database
    first_ctx, first_account = tenant
    second_tenant, second_actor, second_account = uuid4(), uuid4(), uuid4()
    issuer = "route-issuer-" + uuid4().hex
    client_id = "route-client"
    subjects = ("route-first", "route-second")
    roles = ["test_route_" + uuid4().hex[:12] for _ in range(3)]
    passwords = [secrets.token_urlsafe(32) for _ in roles]
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO tenants(id,name) VALUES (%s,'Second route tenant')", (second_tenant,)
        )
        conn.execute(
            "INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES (%s,%s,'owner')",
            (second_tenant, second_actor),
        )
        conn.execute(
            "INSERT INTO mail_accounts(id,tenant_id,provider,address,secret_ref) "
            "VALUES (%s,%s,'fastmail','second-route@example.invalid','synthetic:none')",
            (second_account, second_tenant),
        )
        for tenant_id, actor_id, subject in (
            (first_ctx.tenant_id, first_ctx.actor_id, subjects[0]),
            (second_tenant, second_actor, subjects[1]),
        ):
            conn.execute(
                "INSERT INTO external_identities(id,tenant_id,actor_id,issuer,subject,"
                "client_id,scopes,client_kind) VALUES (%s,%s,%s,%s,%s,%s,"
                "ARRAY['email.search'],'human')",
                (uuid4(), tenant_id, actor_id, issuer, subject, client_id),
            )
        for role, password in zip(roles, passwords, strict=True):
            conn.execute(
                sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD {}").format(
                    sql.Identifier(role), sql.Literal(password)
                )
            )
        grant_identity_lookup(conn, roles[0])
        grant_tenant_runtime(conn, roles[1], first_ctx.tenant_id)
        grant_tenant_runtime(conn, roles[2], second_tenant)
        with pytest.raises(ValueError, match="table or inherited authority"):
            grant_identity_lookup(conn, roles[1])
    lookup_dsn, first_dsn, second_dsn = (
        make_conninfo(admin, user=role, password=password)
        for role, password in zip(roles, passwords, strict=True)
    )
    routed = Store(
        lookup_dsn,
        tenant_dsns={first_ctx.tenant_id: first_dsn, second_tenant: second_dsn},
    )
    with routed.connection() as conn:
        assert conn.execute("SELECT session_user").fetchone() == {"session_user": roles[0]}
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute("SELECT id FROM tenants")
        assert conn.execute(
            "SELECT has_function_privilege(session_user,"
            "'public.lock_recovery_owners(uuid,uuid,uuid)','EXECUTE') AS allowed"
        ).fetchone() == {"allowed": False}
    with pytest.raises(AccessDenied, match="unsafe identity lookup"):
        with Store(shared.dsn, tenant_dsns={first_ctx.tenant_id: first_dsn}).connection():
            pass
    second_ctx = TenantContext(
        second_tenant,
        second_actor,
        frozenset({"email.ingest", "email.search"}),
        uuid4(),
    )
    for dsn, ctx, account, marker in (
        (first_dsn, first_ctx, first_account, "Violet constellation route"),
        (second_dsn, second_ctx, second_account, "Copper harbor route"),
    ):
        Store(dsn).ingest_page(
            ctx,
            account,
            None,
            "route-v1",
            [
                IngestItem(
                    "route-v1",
                    "route-message",
                    "v1",
                    datetime(2026, 9, 25, tzinfo=UTC),
                    f"From: route@example.invalid\r\nSubject: {marker}\r\n\r\n{marker}".encode(),
                )
            ],
            synthetic_only=True,
        )
    verified = {
        "first": VerifiedToken(
            issuer, subjects[0], client_id, datetime.now(UTC) + timedelta(hours=1)
        ),
        "second": VerifiedToken(
            issuer, subjects[1], client_id, datetime.now(UTC) + timedelta(hours=1)
        ),
    }
    verifier = Mock()
    verifier.verify.side_effect = verified.get
    registry = OIDCAuthenticator(routed, verifier)
    client = TestClient(create_app(routed, registry))
    for token, own, foreign in (
        ("first", "Violet", "Copper"),
        ("second", "Copper", "Violet"),
    ):
        for query, expected in ((own, 1), (foreign, 0)):
            response = client.post(
                "/v1/search", json={"query": query}, headers={"Authorization": f"Bearer {token}"}
            )
            assert response.status_code == 200, response.text
            assert len(response.json()["results"]) == expected
    with pytest.raises(AccessDenied, match="route unavailable"):
        with Store(lookup_dsn, tenant_dsns={first_ctx.tenant_id: first_dsn}).transaction(
            second_ctx
        ):
            pass
    with pytest.raises(AccessDenied, match="not bound"):
        with Store(lookup_dsn, tenant_dsns={first_ctx.tenant_id: second_dsn}).transaction(
            first_ctx
        ):
            pass
    with pytest.raises(AccessDenied, match="not bound"):
        with Store(lookup_dsn, tenant_dsns={first_ctx.tenant_id: shared.dsn}).transaction(
            first_ctx
        ):
            pass


def test_tenant_runtime_enrollment_refuses_new_unfenced_table(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID]
) -> None:
    _, admin = database
    ctx, _ = tenant
    role = "test_unfenced_runtime_" + uuid4().hex[:12]
    table = "test_unfenced_" + uuid4().hex[:12]
    with psycopg.connect(admin) as conn:
        conn.execute(
            sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS").format(sql.Identifier(role))
        )
        conn.execute(
            sql.SQL("CREATE TABLE public.{} (tenant_id uuid)").format(sql.Identifier(table))
        )
        conn.execute(
            sql.SQL("ALTER TABLE public.{} ENABLE ROW LEVEL SECURITY").format(sql.Identifier(table))
        )
        conn.execute(
            sql.SQL("ALTER TABLE public.{} FORCE ROW LEVEL SECURITY").format(sql.Identifier(table))
        )
        with pytest.raises(ValueError, match="inventory is incomplete"):
            grant_tenant_runtime(conn, role, ctx.tenant_id)
        assert (
            conn.execute(
                "SELECT 1 FROM masterbrain_tenant_login_bindings WHERE role_name=%s",
                (role,),
            ).fetchone()
            is None
        )
        conn.execute(sql.SQL("DROP TABLE public.{}").format(sql.Identifier(table)))


def test_tenant_runtime_enrollment_refuses_inherited_table_owner(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID]
) -> None:
    _, admin = database
    ctx, _ = tenant
    role = "test_owner_member_" + uuid4().hex[:12]
    owner = "test_table_owner_" + uuid4().hex[:12]
    table = "test_owned_" + uuid4().hex[:12]
    with psycopg.connect(admin) as conn:
        conn.execute(
            sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS").format(sql.Identifier(role))
        )
        conn.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(owner)))
        conn.execute(
            sql.SQL("CREATE TABLE public.{} (tenant_id uuid)").format(sql.Identifier(table))
        )
        conn.execute(
            sql.SQL("ALTER TABLE public.{} OWNER TO {}").format(
                sql.Identifier(table), sql.Identifier(owner)
            )
        )
        conn.execute(sql.SQL("GRANT {} TO {}").format(sql.Identifier(owner), sql.Identifier(role)))
        with pytest.raises(ValueError, match="inherits unsafe authority"):
            grant_tenant_runtime(conn, role, ctx.tenant_id)
        conn.execute(
            sql.SQL("REVOKE {} FROM {}").format(sql.Identifier(owner), sql.Identifier(role))
        )
        conn.execute(sql.SQL("DROP TABLE public.{}").format(sql.Identifier(table)))
        conn.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(owner)))
        conn.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


def item(key: str = "e1", body: str = "Melron investment briefing") -> IngestItem:
    return IngestItem(
        key,
        "provider-message-1",
        key,
        datetime(2026, 9, 19, tzinfo=UTC),
        f"From: alex@example.invalid\r\nSubject: Melron\r\n\r\n{body}".encode(),
    )


def attachment_item(key: str = "attachment-event") -> IngestItem:
    message = EmailMessage()
    message["From"] = "alex@example.invalid"
    message["To"] = "owner@example.invalid"
    message["Subject"] = "Synthetic attachment accounting"
    message.set_content("Parent body without the attachment marker.")
    message.add_attachment(
        "Cobalt attachment covenant",
        subtype="plain",
        filename="first-note.txt",
    )
    message.add_attachment(
        "Cobalt attachment covenant",
        subtype="plain",
        filename="second-note.txt",
    )
    message.add_attachment(
        b"MZ\x00synthetic executable",
        maintype="application",
        subtype="octet-stream",
        filename="dangerous.exe",
    )
    return IngestItem(
        key,
        "provider-attachment-message",
        key,
        datetime(2026, 9, 19, 2, tzinfo=UTC),
        message.as_bytes(),
    )


def test_ingest_search_evidence_replay(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID]
) -> None:
    store, _ = database
    ctx, account = tenant
    assert store.ingest_page(ctx, account, None, "state1", [item()]) == 1
    assert store.ingest_page(ctx, account, None, "state1", [item()]) == 0
    hits = store.search(ctx, SearchRequest(query="Melron"))
    assert len(hits) == 1
    evidence = store.evidence(ctx, hits[0]["evidence_id"])
    assert "investment briefing" in evidence["excerpt"]
    assert evidence["untrusted_content"] is True
    assert len(evidence["excerpt_sha256"]) == 64


def test_stale_cursor_and_key_conflict(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID]
) -> None:
    store, _ = database
    ctx, account = tenant
    store.ingest_page(ctx, account, None, "s1", [item()])
    with pytest.raises(Conflict):
        store.ingest_page(ctx, account, "stale", "s2", [item("e2")])
    with pytest.raises(Conflict):
        store.ingest_page(ctx, account, None, "s1", [item(body="changed")])


def test_failed_page_does_not_checkpoint(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID]
) -> None:
    store, _ = database
    ctx, account = tenant
    store.ingest_page(ctx, account, None, "s1", [item()])
    with pytest.raises(Conflict):
        store.ingest_page(ctx, account, "s1", "s2", [item("new"), item(body="collision")])
    with store.transaction(ctx) as conn:
        assert conn.execute("SELECT count(*) AS n FROM provider_events").fetchone()["n"] == 1
        assert (
            conn.execute("SELECT opaque_cursor FROM sync_cursors").fetchone()["opaque_cursor"]
            == "s1"
        )


def test_update_preserves_old_evidence_and_delete_hides_search(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID]
) -> None:
    store, _ = database
    ctx, account = tenant
    store.ingest_page(ctx, account, None, "s1", [item()])
    old = store.search(ctx, SearchRequest(query="Melron"))[0]["evidence_id"]
    store.ingest_page(ctx, account, "s1", "s2", [item("e2", "Changed newer text")])
    assert "investment briefing" in store.evidence(ctx, old)["excerpt"]
    store.ingest_page(ctx, account, "s2", "s3", [replace(item("e3"), raw=None)])
    assert store.search(ctx, SearchRequest(query="Melron")) == []
    assert store.evidence(ctx, old)["excerpt"]


def test_missing_membership_fails_closed(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID]
) -> None:
    store, _ = database
    ctx, _ = tenant
    with pytest.raises(AccessDenied):
        store.search(replace(ctx, actor_id=uuid4()), SearchRequest(query="Melron"))


def test_owner_database_role_is_rejected(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID]
) -> None:
    _, admin = database
    ctx, _ = tenant
    with pytest.raises(AccessDenied, match="unsafe runtime"):
        Store(admin).search(ctx, SearchRequest(query="Melron"))


def fileos_manifest(root: Path, *, source_id: str = "files_test", hour: int = 1) -> dict[str, Any]:
    return snapshot_tree(
        root,
        source_id=source_id,
        observed_at=datetime(2026, 9, 22, hour, tzinfo=UTC),
    )


ARCHIVE_PROCESSOR = "sandbox-fileos-archive-v1-" + "a" * 64


def archive_fixture(
    core: DataCoreStore,
    ctx: TenantContext,
    root: Path,
    *,
    source_id: str,
    hour: int = 1,
) -> tuple[bytes, dict[str, Any], ArchiveResult]:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("folder/proof.txt", b"hash-only archive proof")
    raw = output.getvalue()
    (root / "fixture.zip").write_bytes(raw)
    manifest = fileos_manifest(root, source_id=source_id, hour=hour)
    core.import_fileos_snapshot(ctx, manifest, uuid4())
    item = manifest["items"][0]
    source = source_for(
        raw,
        item["version_id"],
        item["locator"],
        item["digest"]["value"],
        item["media_type"],
    )
    return raw, manifest, inventory_archive(raw, source)


def archive_image_fixture(
    core: DataCoreStore,
    ctx: TenantContext,
    root: Path,
    *,
    source_id: str,
    hour: int = 1,
    image_suffix: str = ".png",
) -> tuple[bytes, ArchiveMemberTargetRecord]:
    member_locator = f"nested/proof{image_suffix}"
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(member_locator, b"\x89PNG\r\n\x1a\nsynthetic-image-body")
        archive.writestr("sibling.txt", b"must never enter image OCR text")
    raw = output.getvalue()
    (root / "fixture.zip").write_bytes(raw)
    manifest = fileos_manifest(root, source_id=source_id, hour=hour)
    core.import_fileos_snapshot(ctx, manifest, uuid4())
    item = manifest["items"][0]
    source = source_for(
        raw,
        item["version_id"],
        item["locator"],
        item["digest"]["value"],
        item["media_type"],
    )
    inventory = inventory_archive(raw, source)
    recorded = core.record_archive_inventory(ctx, inventory, ARCHIVE_PROCESSOR, uuid4())
    target = core.archive_member_target(ctx, recorded.inventory_id, member_locator)
    return raw, target


def datacore_context(ctx: TenantContext) -> TenantContext:
    return replace(
        ctx,
        scopes=ctx.scopes
        | frozenset(
            {
                "brain.source.ingest",
                "brain.document.publish",
                "brain.index.activate",
                "brain.search",
                "brain.changes.read",
            }
        ),
    )


def email_bridge_config(tmp_path: Path, ctx: TenantContext, code_revision: str) -> Path:
    token = secrets.token_urlsafe(40)
    credentials = tmp_path / "credentials.json"
    token_file = tmp_path / "token"
    config = tmp_path / "bridge.json"
    credentials.write_text(
        json.dumps(
            [
                {
                    "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
                    "tenant_id": str(ctx.tenant_id),
                    "actor_id": str(ctx.actor_id),
                    "scopes": ["brain.source.ingest", "brain.document.publish"],
                    "client_kind": "worker",
                    "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                }
            ]
        )
    )
    token_file.write_text(token)
    for private in (credentials, token_file):
        private.chmod(0o600)
    config.write_text(
        json.dumps(
            {
                "version": 1,
                "credentials_file": str(credentials),
                "token_file": str(token_file),
                "code_revision": code_revision,
            }
        )
    )
    config.chmod(0o600)
    return config


def test_datacore_import_replay_drift_publish_and_search(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID], tmp_path: Path
) -> None:
    store, _ = database
    ctx, _ = tenant
    ctx = datacore_context(ctx)
    core = DataCoreStore(store)
    document = tmp_path / "contract.txt"
    document.write_text(
        "Alpha agreement includes a September renewal commitment.", encoding="utf-8"
    )
    first = fileos_manifest(tmp_path)
    key = uuid4()
    imported = core.import_fileos_snapshot(ctx, first, key)
    assert (imported.new_versions, imported.unchanged_versions) == (1, 0)
    assert core.import_fileos_snapshot(ctx, first, key) == imported
    with pytest.raises(Conflict):
        core.import_fileos_snapshot(ctx, {**first, "policy": {"changed": True}}, key)

    version_id = first["items"][0]["version_id"]
    published = core.publish_text(
        ctx,
        version_id,
        "Alpha agreement includes a September renewal commitment.",
        code_revision="test-revision",
    )
    assert published.changed is True
    assert (
        core.publish_text(
            ctx,
            version_id,
            "Alpha agreement includes a September renewal commitment.",
            code_revision="test-revision",
        ).changed
        is False
    )
    hits = core.search(ctx, "renewal commitment")
    assert len(hits) == 1
    assert hits[0].evidence_id == published.evidence_id
    assert hits[0].locator == "contract.txt"

    document.write_text("Alpha agreement now has an October renewal commitment.", encoding="utf-8")
    second = fileos_manifest(tmp_path, hour=2)
    drift = core.import_fileos_snapshot(ctx, second, uuid4())
    assert (drift.new_versions, drift.unchanged_versions) == (1, 0)
    with store.transaction(ctx) as conn:
        item = conn.execute(
            "SELECT current_version_id FROM brain_source_items WHERE source_id='files_test'"
        ).fetchone()
        assert item["current_version_id"] == second["items"][0]["version_id"]
        assert conn.execute("SELECT count(*) AS n FROM brain_source_versions").fetchone()["n"] == 2


def test_email_bridge_is_replayable_searchable_and_closed(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID]
) -> None:
    store, admin = database
    ctx, account = tenant
    store.ingest_page(ctx, account, None, "bridge-1", [item(body="Cobalt renewal covenant")])
    legacy = store.search(ctx, SearchRequest(query="Cobalt"))[0]["evidence_id"]
    bridge_ctx = datacore_context(ctx)
    core = DataCoreStore(store)
    key = uuid4()

    bridged = core.bridge_current_email_version(
        bridge_ctx, legacy, key, code_revision="email-bridge-test-v1"
    )
    assert bridged.changed is True
    replay = core.bridge_current_email_version(
        bridge_ctx, legacy, key, code_revision="email-bridge-test-v1"
    )
    assert replay == replace(bridged, changed=False)
    second_key = core.bridge_current_email_version(
        bridge_ctx, legacy, uuid4(), code_revision="email-bridge-test-v1"
    )
    assert second_key == replay
    with pytest.raises(Conflict, match="different Email bridge"):
        core.bridge_current_email_version(
            bridge_ctx, uuid4(), key, code_revision="email-bridge-test-v1"
        )
    with pytest.raises(Conflict, match="different provenance"):
        core.bridge_current_email_version(
            bridge_ctx, legacy, uuid4(), code_revision="email-bridge-test-v2"
        )

    hits = core.search(bridge_ctx, "Cobalt renewal")
    assert len(hits) == 1
    assert hits[0].evidence_id == bridged.evidence_id
    assert hits[0].locator.startswith("message/")
    assert "provider-message" not in hits[0].locator
    with store.transaction(bridge_ctx) as conn:
        receipt = conn.execute(
            "SELECT account_id,legacy_version_id,normalizer,chunk_count "
            "FROM brain_email_bridge_receipts WHERE legacy_version_id=%s",
            (legacy,),
        ).fetchone()
        assert receipt == {
            "account_id": account,
            "legacy_version_id": legacy,
            "normalizer": "email-message-v1",
            "chunk_count": bridged.chunks,
        }
        evidence = conn.execute(
            "SELECT storage,retained FROM brain_evidence WHERE id=%s",
            (bridged.evidence_id,),
        ).fetchone()
        assert evidence == {"storage": "inline", "retained": True}
        assert conn.execute("SELECT count(*) AS n FROM raw_objects").fetchone()["n"] == 1
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM brain_provenance p "
                "JOIN brain_provenance_inputs i ON i.tenant_id=p.tenant_id "
                "AND i.provenance_id=p.id WHERE p.output_id=%s AND i.input_id=%s",
                (bridged.document_id, bridged.evidence_id),
            ).fetchone()["n"]
            == 1
        )
    with pytest.raises(psycopg.errors.RaiseException), psycopg.connect(admin) as conn:
        conn.execute(
            "UPDATE brain_email_bridge_receipts SET chunk_count=2 "
            "WHERE tenant_id=%s AND legacy_version_id=%s",
            (ctx.tenant_id, legacy),
        )


def test_email_bridge_rejects_historical_and_hidden_versions(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID]
) -> None:
    store, _ = database
    ctx, account = tenant
    bridge_ctx = datacore_context(ctx)
    core = DataCoreStore(store)
    store.ingest_page(ctx, account, None, "bridge-old", [item(body="Old bridge text")])
    old = store.search(ctx, SearchRequest(query="Old bridge"))[0]["evidence_id"]
    store.ingest_page(
        ctx,
        account,
        "bridge-old",
        "bridge-new",
        [item("bridge-update", body="New bridge text")],
    )
    with pytest.raises(Conflict, match="current Email evidence"):
        core.bridge_current_email_version(
            bridge_ctx, old, uuid4(), code_revision="email-bridge-test-v1"
        )
    current = store.search(ctx, SearchRequest(query="New bridge"))[0]["evidence_id"]
    store.ingest_page(
        ctx,
        account,
        "bridge-new",
        "bridge-deleted",
        [replace(item("bridge-delete"), raw=None)],
    )
    with pytest.raises(Conflict, match="not currently visible"):
        core.bridge_current_email_version(
            bridge_ctx, current, uuid4(), code_revision="email-bridge-test-v1"
        )
    with store.transaction(bridge_ctx) as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM brain_email_bridge_receipts").fetchone()["n"]
            == 0
        )


def test_email_bridge_concurrent_requests_publish_once(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID]
) -> None:
    store, _ = database
    ctx, account = tenant
    store.ingest_page(ctx, account, None, "bridge-race", [item(body="Parallel bridge")])
    legacy = store.search(ctx, SearchRequest(query="Parallel bridge"))[0]["evidence_id"]
    bridge_ctx = datacore_context(ctx)
    core = DataCoreStore(store)
    keys = (uuid4(), uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda key: core.bridge_current_email_version(
                    bridge_ctx, legacy, key, code_revision="email-bridge-test-v1"
                ),
                keys,
            )
        )
    assert sorted(result.changed for result in results) == [False, True]
    assert results[0].document_id == results[1].document_id
    with store.transaction(bridge_ctx) as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM brain_email_bridge_receipts").fetchone()["n"]
            == 1
        )
        assert (
            conn.execute("SELECT count(*) AS n FROM brain_normalized_documents").fetchone()["n"]
            == 1
        )


def test_email_bridge_private_operator_publishes_without_legacy_mutation(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID], tmp_path: Path
) -> None:
    store, _ = database
    ctx, account = tenant
    store.ingest_page(ctx, account, None, "bridge-command", [item(body="Operator bridge")])
    legacy = store.search(ctx, SearchRequest(query="Operator bridge"))[0]["evidence_id"]
    config = email_bridge_config(tmp_path, ctx, "email-bridge-command-test-v1")
    before = store.evidence(ctx, legacy)
    result = run_email_bridge_controller(config, store.dsn, legacy, uuid4())
    assert result["recorded"] is True
    assert result["source_effects"] is False
    assert DataCoreStore(store).search(datacore_context(ctx), "Operator bridge")
    assert store.evidence(ctx, legacy) == before


def test_email_bridge_plan_is_stable_bounded_and_labels_existing_bridge(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID]
) -> None:
    store, _ = database
    ctx, account = tenant
    bridge_ctx = datacore_context(ctx)
    core = DataCoreStore(store)
    messages = [
        replace(
            item(f"plan-{ordinal}", body=f"Bridge plan body {ordinal}"),
            provider_id=f"provider-plan-{ordinal}",
        )
        for ordinal in range(3)
    ]
    store.ingest_page(ctx, account, None, "bridge-plan-page", messages)
    first = core.email_bridge_plan(bridge_ctx, account, limit=2)
    assert first["source_effects"] is False and first["data_effects"] is False
    assert len(first["results"]) == 2 and first["next_cursor"] is not None
    assert all(not row["already_bridged"] for row in first["results"])
    cursor = UUID(first["next_cursor"])
    second = core.email_bridge_plan(bridge_ctx, account, after=cursor, limit=2)
    assert len(second["results"]) == 1 and second["next_cursor"] is None
    selected = UUID(first["results"][0]["legacy_version_id"])
    core.bridge_current_email_version(
        bridge_ctx, selected, uuid4(), code_revision="email-bridge-plan-test-v1"
    )
    replayed_plan = core.email_bridge_plan(bridge_ctx, account, limit=3)
    by_version = {row["legacy_version_id"]: row for row in replayed_plan["results"]}
    assert by_version[str(selected)]["already_bridged"] is True
    assert sum(row["already_bridged"] for row in replayed_plan["results"]) == 1
    with pytest.raises(NotFound):
        core.email_bridge_plan(bridge_ctx, uuid4())
    with pytest.raises(NotFound):
        core.email_bridge_plan(bridge_ctx, account, after=uuid4())
    with pytest.raises(ValueError, match="limit"):
        core.email_bridge_plan(bridge_ctx, account, limit=101)


def test_email_bridge_batch_fail_stop_and_exact_retry(
    database: tuple[Store, str],
    tenant: tuple[TenantContext, UUID],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _ = database
    ctx, account = tenant
    bridge_ctx = datacore_context(ctx)
    core = DataCoreStore(store)
    code_revision = "email-bridge-batch-test-v1"
    config = email_bridge_config(tmp_path, ctx, code_revision)
    messages = [
        replace(
            item(f"batch-{ordinal}", body=f"Sealed batch body {ordinal}"),
            provider_id=f"provider-batch-{ordinal}",
        )
        for ordinal in range(3)
    ]
    store.ingest_page(ctx, account, None, "bridge-batch-page", messages)
    preview = core.email_bridge_plan(bridge_ctx, account, limit=3)["results"]
    items = [
        EmailBridgeBatchItem(
            legacy_version_id=UUID(row["legacy_version_id"]),
            idempotency_key=uuid4(),
        )
        for row in preview
    ]
    with pytest.raises(Conflict, match="sealed batch account"):
        core.bridge_current_email_version(
            bridge_ctx,
            items[0].legacy_version_id,
            uuid4(),
            code_revision=code_revision,
            expected_account_id=uuid4(),
        )
    digest = email_bridge_batch_sha256(1, account, code_revision, items)
    plan = tmp_path / "batch-plan.json"
    plan.write_text(
        json.dumps(
            {
                "version": 1,
                "account_id": str(account),
                "code_revision": code_revision,
                "items": [item.model_dump(mode="json") for item in items],
                "plan_sha256": digest,
            }
        )
    )
    plan.chmod(0o600)
    checked = run_email_bridge_batch_controller(config, plan, store.dsn, check=True)
    assert checked["execution_verified"] is False and checked["requested"] == 3
    with store.transaction(bridge_ctx) as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM brain_email_bridge_receipts").fetchone()["n"]
            == 0
        )

    original = DataCoreStore.bridge_current_email_version
    calls = 0

    def fail_second(self: DataCoreStore, *args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise Conflict("synthetic mid-batch refusal")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(DataCoreStore, "bridge_current_email_version", fail_second)
    stopped = run_email_bridge_batch_controller(config, plan, store.dsn)
    assert stopped["complete"] is False
    assert stopped["completed"] == 1 and stopped["failed_version_id"] == str(
        items[1].legacy_version_id
    )
    with store.transaction(bridge_ctx) as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM brain_email_bridge_receipts").fetchone()["n"]
            == 1
        )

    monkeypatch.setattr(DataCoreStore, "bridge_current_email_version", original)
    completed = run_email_bridge_batch_controller(config, plan, store.dsn)
    assert completed["complete"] is True
    assert completed["recorded"] == 2 and completed["replayed"] == 1
    assert [row["legacy_version_id"] for row in completed["results"]] == [
        str(item.legacy_version_id) for item in items
    ]
    with store.transaction(bridge_ctx) as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM brain_email_bridge_receipts").fetchone()["n"]
            == 3
        )


def test_email_attachment_batch_fail_stop_account_fence_and_exact_retry(
    database: tuple[Store, str],
    tenant: tuple[TenantContext, UUID],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _ = database
    ctx, account = tenant
    bridge_ctx = datacore_context(ctx)
    core = DataCoreStore(store)
    code_revision = "email-attachment-batch-test-v1"
    config = email_bridge_config(tmp_path, ctx, code_revision)
    store.ingest_page(ctx, account, None, "attachment-batch-page", [attachment_item()])
    parent_id = store.search(ctx, SearchRequest(query="Synthetic attachment accounting"))[0][
        "evidence_id"
    ]
    core.bridge_current_email_version(bridge_ctx, parent_id, uuid4(), code_revision=code_revision)
    preview = core.email_part_bridge_plan(bridge_ctx, account, "attachment")["results"]
    assert len(preview) == 3
    items = [
        EmailPartBridgeBatchItem(
            legacy_id=UUID(row["legacy_attachment_id"]), idempotency_key=uuid4()
        )
        for row in preview
    ]
    with pytest.raises(Conflict, match="sealed batch account"):
        core.bridge_email_attachment(
            bridge_ctx,
            items[0].legacy_id,
            uuid4(),
            code_revision=code_revision,
            expected_account_id=uuid4(),
        )
    digest = email_part_bridge_batch_sha256(1, account, "attachment", code_revision, items)
    plan = tmp_path / "attachment-batch.json"
    plan.write_text(
        json.dumps(
            {
                "version": 1,
                "account_id": str(account),
                "kind": "attachment",
                "code_revision": code_revision,
                "items": [item.model_dump(mode="json") for item in items],
                "plan_sha256": digest,
            }
        )
    )
    plan.chmod(0o600)
    assert (
        run_email_part_bridge_batch_controller(config, plan, store.dsn, check=True)["data_effects"]
        is False
    )
    original = DataCoreStore.bridge_email_attachment
    calls = 0

    def fail_second(self: DataCoreStore, *args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise Conflict("synthetic mid-batch refusal")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(DataCoreStore, "bridge_email_attachment", fail_second)
    stopped = run_email_part_bridge_batch_controller(config, plan, store.dsn)
    assert stopped["complete"] is False and stopped["completed"] == 1
    with store.transaction(bridge_ctx) as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM brain_email_attachment_bridge_receipts"
            ).fetchone()["n"]
            == 1
        )
    monkeypatch.setattr(DataCoreStore, "bridge_email_attachment", original)
    completed = run_email_part_bridge_batch_controller(config, plan, store.dsn)
    assert completed["complete"] is True
    assert completed["recorded"] == 2 and completed["replayed"] == 1
    with store.transaction(bridge_ctx) as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM brain_email_attachment_bridge_receipts"
            ).fetchone()["n"]
            == 3
        )


def test_current_email_search_tracks_legacy_update_and_delete(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID]
) -> None:
    store, _ = database
    ctx, account = tenant
    bridge_ctx = datacore_context(ctx)
    core = DataCoreStore(store)
    store.ingest_page(ctx, account, None, "current-email-1", [item(body="Amber current term")])
    first = store.search(ctx, SearchRequest(query="Amber current"))[0]["evidence_id"]
    first_bridge = core.bridge_current_email_version(
        bridge_ctx, first, uuid4(), code_revision="current-email-search-v1"
    )
    first_hits = core.search_current_email(bridge_ctx, "Amber current")
    assert [hit.evidence_id for hit in first_hits] == [first_bridge.evidence_id]
    first_family = core.search_current_email_family(bridge_ctx, "Amber current")
    assert [hit.evidence_id for hit in first_family.messages] == [first_bridge.evidence_id]
    assert first_family.attachments == () and first_family.documents == ()
    first_coverage = next(
        row
        for row in core.current_coverage(bridge_ctx)["results"]
        if row["source_id"] == first_bridge.source_id
    )
    assert first_coverage["current_counts"]["messages"] == 1
    first_plan = core.email_bridge_plan(bridge_ctx, account)["results"]
    assert first_plan == [
        {
            "legacy_version_id": str(first),
            "recorded_at": first_plan[0]["recorded_at"],
            "already_bridged": True,
        }
    ]

    store.ingest_page(
        ctx,
        account,
        "current-email-1",
        "current-email-2",
        [item("current-email-update", body="Violet replacement term")],
    )
    assert core.search_current_email(bridge_ctx, "Amber current") == []
    assert core.search_current_email_family(bridge_ctx, "Amber current").messages == ()
    assert core.search_current_email(bridge_ctx, "Violet replacement") == []
    updated_coverage = next(
        row
        for row in core.current_coverage(bridge_ctx)["results"]
        if row["source_id"] == first_bridge.source_id
    )
    assert updated_coverage["current_counts"]["messages"] == 0
    updated_plan = core.email_bridge_plan(bridge_ctx, account)["results"]
    assert len(updated_plan) == 1
    assert updated_plan[0]["legacy_version_id"] != str(first)
    assert updated_plan[0]["already_bridged"] is False
    second = store.search(ctx, SearchRequest(query="Violet replacement"))[0]["evidence_id"]
    assert updated_plan[0]["legacy_version_id"] == str(second)
    second_bridge = core.bridge_current_email_version(
        bridge_ctx, second, uuid4(), code_revision="current-email-search-v1"
    )
    second_hits = core.search_current_email(bridge_ctx, "Violet replacement")
    assert [hit.evidence_id for hit in second_hits] == [second_bridge.evidence_id]
    assert core.search_current_email(bridge_ctx, "Violet replacement", limit=1) == second_hits
    second_family = core.search_current_email_family(bridge_ctx, "Violet replacement")
    assert [hit.evidence_id for hit in second_family.messages] == [second_bridge.evidence_id]
    current_coverage = next(
        row
        for row in core.current_coverage(bridge_ctx)["results"]
        if row["source_id"] == second_bridge.source_id
    )
    assert current_coverage["current_counts"]["messages"] == 1
    current_plan = core.email_bridge_plan(bridge_ctx, account)["results"]
    assert len(current_plan) == 1
    assert current_plan[0]["legacy_version_id"] == str(second)
    assert current_plan[0]["already_bridged"] is True
    with store.transaction(ctx) as conn:
        conn.execute(
            "UPDATE messages SET quarantined=true WHERE account_id=%s "
            "AND raw_sha256=(SELECT raw_sha256 FROM message_versions WHERE id=%s)",
            (account, second),
        )
    quarantined = core.search_current_email_family(bridge_ctx, "Violet replacement")
    assert quarantined.messages == () and quarantined.attachments == ()
    assert quarantined.documents == ()
    quarantined_coverage = next(
        row
        for row in core.current_coverage(bridge_ctx)["results"]
        if row["source_id"] == second_bridge.source_id
    )
    assert quarantined_coverage["current_counts"]["messages"] == 0
    assert core.email_bridge_plan(bridge_ctx, account)["results"] == []
    with store.transaction(ctx) as conn:
        conn.execute("UPDATE messages SET quarantined=false WHERE account_id=%s", (account,))
    restored_plan = core.email_bridge_plan(bridge_ctx, account)["results"]
    assert len(restored_plan) == 1 and restored_plan[0]["already_bridged"] is True

    store.ingest_page(
        ctx,
        account,
        "current-email-2",
        "current-email-deleted",
        [replace(item("current-email-delete"), raw=None)],
    )
    assert core.search_current_email(bridge_ctx, "Violet replacement") == []
    deleted = core.search_current_email_family(bridge_ctx, "Violet replacement")
    assert deleted.messages == () and deleted.attachments == () and deleted.documents == ()
    deleted_coverage = next(
        row
        for row in core.current_coverage(bridge_ctx)["results"]
        if row["source_id"] == second_bridge.source_id
    )
    assert deleted_coverage["current_counts"]["messages"] == 0
    assert core.email_bridge_plan(bridge_ctx, account)["results"] == []
    assert core.search(bridge_ctx, "Violet replacement")


def test_email_attachment_bridge_preserves_occurrences_and_outcomes(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID]
) -> None:
    store, admin = database
    ctx, account = tenant
    bridge_ctx = datacore_context(ctx)
    core = DataCoreStore(store)
    store.ingest_page(ctx, account, None, "attachment-page", [attachment_item()])
    legacy_parent = store.search(ctx, SearchRequest(query="Synthetic attachment accounting"))[0][
        "evidence_id"
    ]
    parent = core.bridge_current_email_version(
        bridge_ctx, legacy_parent, uuid4(), code_revision="attachment-bridge-test-v1"
    )
    attachment_rows = store.evidence(ctx, legacy_parent)["attachments"]
    assert len(attachment_rows) == 3
    results = [
        core.bridge_email_attachment(
            bridge_ctx,
            row["id"],
            uuid4(),
            code_revision="attachment-bridge-test-v1",
        )
        for row in attachment_rows
    ]
    extracted = [result for result in results if result.outcome == "extracted"]
    deferred = [result for result in results if result.outcome == "deferred"]
    assert len(extracted) == 2
    assert len(deferred) == 1
    assert all(result.document_id is not None and result.chunks == 1 for result in extracted)
    assert deferred[0].document_id is None and deferred[0].chunks == 0
    assert len({result.evidence_id for result in extracted}) == 2
    hits = core.search(bridge_ctx, "Cobalt attachment covenant")
    assert {hit.evidence_id for hit in hits} == {result.evidence_id for result in extracted}
    family = core.search_current_email_family(
        bridge_ctx,
        "Cobalt attachment covenant",
        message_limit=1,
        attachment_limit=1,
        document_limit=1,
    )
    assert family.messages == () and family.documents == ()
    assert len(family.attachments) == 1
    all_occurrences = core.search_current_email_family(
        bridge_ctx, "Cobalt attachment covenant", attachment_limit=2
    )
    assert {hit.evidence_id for hit in all_occurrences.attachments} == {
        result.evidence_id for result in extracted
    }

    replay = core.bridge_email_attachment(
        bridge_ctx,
        attachment_rows[0]["id"],
        uuid4(),
        code_revision="attachment-bridge-test-v1",
    )
    assert replay.changed is False
    with store.transaction(bridge_ctx) as conn:
        parts = conn.execute(
            "SELECT parent_evidence_id,evidence_id,sha256,status FROM brain_parts "
            "ORDER BY part_path"
        ).fetchall()
        assert len(parts) == 3
        assert all(row["parent_evidence_id"] == parent.evidence_id for row in parts)
        assert parts[0]["sha256"] == parts[1]["sha256"]
        assert parts[0]["evidence_id"] != parts[1]["evidence_id"]
        receipts = conn.execute(
            "SELECT outcome,document_id,chunk_count FROM "
            "brain_email_attachment_bridge_receipts ORDER BY outcome,legacy_attachment_id"
        ).fetchall()
        assert sum(row["outcome"] == "extracted" for row in receipts) == 2
        assert sum(row["outcome"] == "deferred" for row in receipts) == 1
    with pytest.raises(psycopg.errors.RaiseException), psycopg.connect(admin) as conn:
        conn.execute(
            "UPDATE brain_parts SET reason='rewritten' WHERE tenant_id=%s",
            (ctx.tenant_id,),
        )


def test_email_attachment_bridge_rejects_historical_parent(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID]
) -> None:
    store, _ = database
    ctx, account = tenant
    bridge_ctx = datacore_context(ctx)
    core = DataCoreStore(store)
    store.ingest_page(ctx, account, None, "attachment-old", [attachment_item("attachment-old")])
    legacy_parent = store.search(ctx, SearchRequest(query="Synthetic attachment accounting"))[0][
        "evidence_id"
    ]
    attachment_id = store.evidence(ctx, legacy_parent)["attachments"][0]["id"]
    core.bridge_current_email_version(
        bridge_ctx, legacy_parent, uuid4(), code_revision="attachment-bridge-test-v1"
    )
    store.ingest_page(
        ctx,
        account,
        "attachment-old",
        "attachment-new",
        [
            replace(
                item("attachment-replacement", body="Replacement without attachments"),
                provider_id="provider-attachment-message",
            )
        ],
    )
    with pytest.raises(Conflict, match="historical"):
        core.bridge_email_attachment(
            bridge_ctx,
            attachment_id,
            uuid4(),
            code_revision="attachment-bridge-test-v1",
        )
    family = core.search_current_email_family(bridge_ctx, "Synthetic attachment accounting")
    assert family.messages == () and family.attachments == () and family.documents == ()
    with store.transaction(bridge_ctx) as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM brain_email_attachment_bridge_receipts"
            ).fetchone()["n"]
            == 0
        )


def test_datacore_invalid_manifest_is_atomic(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID], tmp_path: Path
) -> None:
    store, _ = database
    ctx, _ = tenant
    ctx = datacore_context(ctx)
    core = DataCoreStore(store)
    (tmp_path / "one.txt").write_text("one", encoding="utf-8")
    (tmp_path / "two.txt").write_text("two", encoding="utf-8")
    manifest = fileos_manifest(tmp_path, source_id="files_atomic")
    manifest["items"][1]["version_id"] = "version_" + "0" * 32
    with pytest.raises(ValueError, match="identity"):
        core.import_fileos_snapshot(ctx, manifest, uuid4())
    with store.transaction(ctx) as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM brain_sources WHERE id='files_atomic'"
            ).fetchone()["n"]
            == 0
        )


def test_datacore_concurrent_replay_creates_one_version(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID], tmp_path: Path
) -> None:
    store, _ = database
    ctx, _ = tenant
    ctx = datacore_context(ctx)
    core = DataCoreStore(store)
    (tmp_path / "one.txt").write_text("same", encoding="utf-8")
    manifest = fileos_manifest(tmp_path, source_id="files_concurrent")
    key = uuid4()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda _: core.import_fileos_snapshot(ctx, manifest, key), range(2))
        )
    assert results[0] == results[1]
    with store.transaction(ctx) as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM brain_source_versions WHERE source_id='files_concurrent'"
            ).fetchone()["n"]
            == 1
        )
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM brain_change_events WHERE source_id='files_concurrent'"
            ).fetchone()["n"]
            == 1
        )


def test_datacore_rls_and_immutability(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID], tmp_path: Path
) -> None:
    store, admin = database
    ctx, _ = tenant
    ctx = datacore_context(ctx)
    core = DataCoreStore(store)
    (tmp_path / "private.txt").write_text("Tenant one private evidence", encoding="utf-8")
    manifest = fileos_manifest(tmp_path, source_id="files_private")
    core.import_fileos_snapshot(ctx, manifest, uuid4())
    version_id = manifest["items"][0]["version_id"]
    with pytest.raises(psycopg.errors.InsufficientPrivilege), store.transaction(ctx) as conn:
        conn.execute(
            "UPDATE brain_source_versions SET media_type='text/html' WHERE id=%s", (version_id,)
        )

    other_tenant, other_actor = uuid4(), uuid4()
    with psycopg.connect(admin) as conn:
        conn.execute("INSERT INTO tenants(id,name) VALUES (%s,'Other synthetic')", (other_tenant,))
        conn.execute(
            "INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES (%s,%s,'owner')",
            (other_tenant, other_actor),
        )
    other = replace(ctx, tenant_id=other_tenant, actor_id=other_actor, request_id=uuid4())
    with store.transaction(other) as conn:
        assert conn.execute("SELECT count(*) AS n FROM brain_source_versions").fetchone()["n"] == 0
    assert core.search(other, "private evidence") == []


def test_archive_manifest_record_replay_concurrency_and_no_search_effect(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID], tmp_path: Path
) -> None:
    store, _ = database
    ctx, _ = tenant
    ctx = datacore_context(ctx)
    core = DataCoreStore(store)
    _, _, result = archive_fixture(core, ctx, tmp_path, source_id="files_archive_manifest")
    before_search = core.search(ctx, "hash-only archive proof")
    with store.transaction(ctx) as conn:
        before_changes = conn.execute(
            "SELECT count(*) AS n FROM brain_change_events WHERE source_id=%s",
            ("files_archive_manifest",),
        ).fetchone()["n"]

    key = uuid4()
    first = core.record_archive_inventory(ctx, result, ARCHIVE_PROCESSOR, key)
    replay = core.record_archive_inventory(ctx, result, ARCHIVE_PROCESSOR, key)
    assert first.changed is True and replay == replace(first, changed=False)
    with ThreadPoolExecutor(max_workers=2) as pool:
        concurrent = list(
            pool.map(
                lambda _: core.record_archive_inventory(ctx, result, ARCHIVE_PROCESSOR, uuid4()),
                range(2),
            )
        )
    assert all(item == replace(first, changed=False) for item in concurrent)
    with store.transaction(ctx) as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM brain_archive_inventories").fetchone()["n"] == 1
        )
        assert conn.execute("SELECT count(*) AS n FROM brain_archive_members").fetchone()[
            "n"
        ] == len(result.members)
        assert (
            conn.execute("SELECT count(*) AS n FROM brain_archive_inventory_receipts").fetchone()[
                "n"
            ]
            == 3
        )
        after_changes = conn.execute(
            "SELECT count(*) AS n FROM brain_change_events WHERE source_id=%s",
            ("files_archive_manifest",),
        ).fetchone()["n"]
    assert core.search(ctx, "hash-only archive proof") == before_search == []
    assert after_changes == before_changes


def test_archive_sealed_ledger_rejects_late_members_and_skips(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID], tmp_path: Path
) -> None:
    store, admin = database
    ctx, _ = tenant
    ctx = datacore_context(ctx)
    core = DataCoreStore(store)
    _, _, result = archive_fixture(core, ctx, tmp_path, source_id="files_late_archive_child")
    recorded = core.record_archive_inventory(ctx, result, ARCHIVE_PROCESSOR, uuid4())
    with psycopg.connect(admin) as conn:
        before = conn.execute(
            "SELECT (SELECT count(*) FROM brain_archive_members WHERE tenant_id=%s "
            "AND inventory_id=%s), (SELECT count(*) FROM brain_archive_skips "
            "WHERE tenant_id=%s AND inventory_id=%s)",
            (ctx.tenant_id, recorded.inventory_id, ctx.tenant_id, recorded.inventory_id),
        ).fetchone()
    with pytest.raises(psycopg.errors.RaiseException, match="invalid archive inventory ledger"):
        with psycopg.connect(admin) as conn:
            conn.execute(
                "INSERT INTO brain_archive_members(tenant_id,inventory_id,ordinal,locator,"
                "sha256,declared_size,observed_size,media_hint,depth,is_container) "
                "VALUES (%s,%s,1999,'late.bin',%s,1,1,'application/octet-stream',0,false)",
                (ctx.tenant_id, recorded.inventory_id, "a" * 64),
            )
    with pytest.raises(psycopg.errors.RaiseException, match="invalid archive inventory ledger"):
        with psycopg.connect(admin) as conn:
            conn.execute(
                "INSERT INTO brain_archive_skips "
                "(tenant_id,inventory_id,ordinal,locator,reason,depth) "
                "VALUES (%s,%s,2000,'late.skip','unreadable',0)",
                (ctx.tenant_id, recorded.inventory_id),
            )
    with psycopg.connect(admin) as conn:
        after = conn.execute(
            "SELECT (SELECT count(*) FROM brain_archive_members WHERE tenant_id=%s "
            "AND inventory_id=%s), (SELECT count(*) FROM brain_archive_skips "
            "WHERE tenant_id=%s AND inventory_id=%s)",
            (ctx.tenant_id, recorded.inventory_id, ctx.tenant_id, recorded.inventory_id),
        ).fetchone()
    assert after == before


def test_archive_derivative_parent_and_provenance_database_links(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID], tmp_path: Path
) -> None:
    store, admin = database
    ctx, _ = tenant
    ctx = datacore_context(ctx)
    core = DataCoreStore(store)
    _, _, result = archive_fixture(core, ctx, tmp_path, source_id="files_archive_fk")
    recorded = core.record_archive_inventory(ctx, result, ARCHIVE_PROCESSOR, uuid4())
    target = core.archive_member_target(ctx, recorded.inventory_id, result.members[0].locator)
    extraction = ExtractionResult(
        archive_member_version_id(target),
        target.member_locator,
        ExtractionStatus.EXTRACTED,
        "synthetic archive parent link",
        metadata={"extractor_version": "fileos-text-v1"},
    )
    publish_extracted_archive_member_text(
        core, ctx, target, extraction, code_revision="test-revision", idempotency_key=uuid4()
    )
    with psycopg.connect(admin) as conn:
        constraints = conn.execute(
            "SELECT conrelid::regclass::text,convalidated,"
            "pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conname IN ('brain_archive_text_parent_inventory_fk',"
            "'brain_archive_document_parent_inventory_fk',"
            "'brain_archive_image_parent_inventory_fk') ORDER BY conname"
        ).fetchall()
    assert len(constraints) == 3
    assert all(
        validated
        and "FOREIGN KEY (tenant_id, inventory_id, parent_source_version_id)" in definition
        and "REFERENCES brain_archive_inventories(tenant_id, id, source_version_id)" in definition
        for _, validated, definition in constraints
    )
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with psycopg.connect(admin) as conn:
            conn.execute(
                "INSERT INTO brain_archive_member_text_receipts "
                "(tenant_id,actor_id,idempotency_key,inventory_id,member_locator,"
                "parent_source_version_id,parent_evidence_id,source_id,item_id,version_id,"
                "evidence_id,document_id,normalizer,chunk_count,code_revision,request_hash) "
                "SELECT tenant_id,actor_id,%s,inventory_id,member_locator,version_id,"
                "parent_evidence_id,source_id,item_id,version_id,evidence_id,document_id,"
                "normalizer,chunk_count,code_revision,request_hash "
                "FROM brain_archive_member_text_receipts WHERE tenant_id=%s "
                "AND inventory_id=%s LIMIT 1",
                (uuid4(), ctx.tenant_id, recorded.inventory_id),
            )
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with psycopg.connect(admin) as conn:
            conn.execute(
                "INSERT INTO brain_provenance(tenant_id,id,output_id,transform,transform_version,"
                "code_revision,configuration_sha256,created_at) "
                "VALUES (%s,%s,%s,'synthetic-link','v1','test-revision',%s,now())",
                (ctx.tenant_id, "provenance_" + uuid4().hex, "missing_" + uuid4().hex, "a" * 64),
            )


def test_archive_manifest_rejects_terminal_drift_and_stale_parent(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID], tmp_path: Path
) -> None:
    store, _ = database
    ctx, _ = tenant
    ctx = datacore_context(ctx)
    core = DataCoreStore(store)
    raw, _, result = archive_fixture(core, ctx, tmp_path, source_id="files_archive_fences")
    bomb_raw = io.BytesIO()
    with zipfile.ZipFile(bomb_raw, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("bomb.bin", b"0" * (1024 * 1024))
    bomb = bomb_raw.getvalue()
    bomb_source = source_for(
        bomb,
        "version_" + hashlib.sha256(bomb).hexdigest()[:32],
        "bomb.zip",
        hashlib.sha256(bomb).hexdigest(),
        "application/zip",
    )
    with pytest.raises(ValueError, match="accepted archive"):
        core.record_archive_inventory(
            ctx, inventory_archive(bomb, bomb_source), ARCHIVE_PROCESSOR, uuid4()
        )

    key = uuid4()
    core.record_archive_inventory(ctx, result, ARCHIVE_PROCESSOR, key)
    drift = replace(
        result,
        status="partial",
        reason="bounded_archive_partial_v1",
        skipped=(ArchiveSkip("diagnostic", "unreadable", 0, None),),
    )
    with pytest.raises(Conflict, match="idempotency key"):
        core.record_archive_inventory(ctx, drift, ARCHIVE_PROCESSOR, key)
    with pytest.raises(Conflict, match="different manifest"):
        core.record_archive_inventory(ctx, drift, ARCHIVE_PROCESSOR, uuid4())

    (tmp_path / "fixture.zip").write_bytes(raw + b"changed")
    newer = fileos_manifest(tmp_path, source_id="files_archive_fences", hour=2)
    core.import_fileos_snapshot(ctx, newer, uuid4())
    with pytest.raises(Conflict, match="historical"):
        core.record_archive_inventory(
            ctx,
            result,
            "sandbox-fileos-archive-v1-" + "b" * 64,
            uuid4(),
        )


def test_archive_manifest_forced_rls_and_append_only(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID], tmp_path: Path
) -> None:
    store, admin = database
    ctx, _ = tenant
    ctx = datacore_context(ctx)
    core = DataCoreStore(store)
    _, _, result = archive_fixture(core, ctx, tmp_path, source_id="files_archive_private")
    recorded = core.record_archive_inventory(ctx, result, ARCHIVE_PROCESSOR, uuid4())
    with pytest.raises(psycopg.errors.InsufficientPrivilege), store.transaction(ctx) as conn:
        conn.execute(
            "UPDATE brain_archive_inventories SET status='partial' WHERE id=%s",
            (recorded.inventory_id,),
        )

    other_tenant, other_actor = uuid4(), uuid4()
    with psycopg.connect(admin) as conn:
        conn.execute("INSERT INTO tenants(id,name) VALUES (%s,'Archive other')", (other_tenant,))
        conn.execute(
            "INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES (%s,%s,'owner')",
            (other_tenant, other_actor),
        )
    other = replace(ctx, tenant_id=other_tenant, actor_id=other_actor, request_id=uuid4())
    with store.transaction(other) as conn:
        for table in (
            "brain_archive_inventories",
            "brain_archive_members",
            "brain_archive_skips",
            "brain_archive_inventory_receipts",
            "brain_archive_member_text_receipts",
        ):
            assert conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"] == 0


def test_archive_member_target_requires_current_non_container_and_rls(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID], tmp_path: Path
) -> None:
    store, admin = database
    ctx, _ = tenant
    ctx = datacore_context(ctx)
    core = DataCoreStore(store)
    raw, _, result = archive_fixture(core, ctx, tmp_path, source_id="files_member_target")
    recorded = core.record_archive_inventory(ctx, result, ARCHIVE_PROCESSOR, uuid4())
    member = result.members[0]
    target = core.archive_member_target(ctx, recorded.inventory_id, member.locator)
    assert (
        target.source_version_id,
        target.source_sha256,
        target.source_size_bytes,
        target.member_locator,
        target.member_sha256,
        target.member_size_bytes,
    ) == (
        result.source.version_id,
        result.source.sha256,
        len(raw),
        member.locator,
        member.sha256,
        member.observed_size,
    )

    other_tenant, other_actor = uuid4(), uuid4()
    with psycopg.connect(admin) as conn:
        conn.execute("INSERT INTO tenants(id,name) VALUES (%s,'Member other')", (other_tenant,))
        conn.execute(
            "INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES (%s,%s,'owner')",
            (other_tenant, other_actor),
        )
    other = replace(ctx, tenant_id=other_tenant, actor_id=other_actor, request_id=uuid4())
    with pytest.raises(NotFound):
        core.archive_member_target(other, recorded.inventory_id, member.locator)

    (tmp_path / "fixture.zip").write_bytes(raw + b"new version")
    newer = fileos_manifest(tmp_path, source_id="files_member_target", hour=2)
    core.import_fileos_snapshot(ctx, newer, uuid4())
    with pytest.raises(NotFound):
        core.archive_member_target(ctx, recorded.inventory_id, member.locator)


def test_archive_member_target_refuses_intermediate_container(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID], tmp_path: Path
) -> None:
    store, _ = database
    ctx, _ = tenant
    ctx = datacore_context(ctx)
    core = DataCoreStore(store)
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as archive:
        archive.writestr("proof.txt", b"nested")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("inner.zip", inner.getvalue())
    raw = output.getvalue()
    (tmp_path / "nested.zip").write_bytes(raw)
    manifest = fileos_manifest(tmp_path, source_id="files_member_container")
    core.import_fileos_snapshot(ctx, manifest, uuid4())
    item = next(item for item in manifest["items"] if item["locator"] == "nested.zip")
    source = source_for(
        raw,
        item["version_id"],
        item["locator"],
        item["digest"]["value"],
        item["media_type"],
    )
    result = inventory_archive(raw, source)
    recorded = core.record_archive_inventory(ctx, result, ARCHIVE_PROCESSOR, uuid4())
    with pytest.raises(NotFound):
        core.archive_member_target(ctx, recorded.inventory_id, "inner.zip")


def test_archive_member_text_publication_is_distinct_replayable_and_not_current_search(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID], tmp_path: Path
) -> None:
    store, _ = database
    ctx, _ = tenant
    ctx = datacore_context(ctx)
    core = DataCoreStore(store)
    raw, _, result = archive_fixture(core, ctx, tmp_path, source_id="files_member_text")
    recorded = core.record_archive_inventory(ctx, result, ARCHIVE_PROCESSOR, uuid4())
    member = result.members[0]
    target = core.archive_member_target(ctx, recorded.inventory_id, member.locator)
    extraction = ExtractionResult(
        archive_member_version_id(target),
        member.locator,
        ExtractionStatus.EXTRACTED,
        "explicit archive derivative searchable proof",
        metadata={"extractor_version": "fileos-text-v1"},
    )
    key = uuid4()
    first = publish_extracted_archive_member_text(
        core, ctx, target, extraction, code_revision="test-revision", idempotency_key=key
    )
    replay = publish_extracted_archive_member_text(
        core, ctx, target, extraction, code_revision="test-revision", idempotency_key=key
    )
    second_key = publish_extracted_archive_member_text(
        core, ctx, target, extraction, code_revision="test-revision", idempotency_key=uuid4()
    )
    assert first.changed is True
    assert replay == replace(first, changed=False) == second_key
    assert first.version_id != result.source.version_id
    assert core.search(ctx, "archive derivative searchable")[0].evidence_id == first.evidence_id
    assert core.search_current_fileos(ctx, "archive derivative searchable") == []
    current = core.search_current_archive_members(ctx, "archive derivative searchable")
    assert [hit.evidence_id for hit in current] == [first.evidence_id]
    assert current[0].locator.startswith("archive-member/archiveitem_")
    assert member.locator not in current[0].locator
    with store.transaction(ctx) as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM brain_archive_member_text_receipts").fetchone()[
                "n"
            ]
            == 2
        )
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM brain_source_versions WHERE id=%s", (first.version_id,)
            ).fetchone()["n"]
            == 1
        )
    with pytest.raises(psycopg.errors.InsufficientPrivilege), store.transaction(ctx) as conn:
        conn.execute(
            "UPDATE brain_archive_member_text_receipts SET code_revision='changed' "
            "WHERE inventory_id=%s",
            (target.inventory_id,),
        )
    changed_extraction = replace(extraction, text="different archive derivative")
    with pytest.raises(Conflict, match="idempotency key"):
        publish_extracted_archive_member_text(
            core,
            ctx,
            target,
            changed_extraction,
            code_revision="test-revision",
            idempotency_key=key,
        )
    with pytest.raises(Conflict, match="different provenance"):
        publish_extracted_archive_member_text(
            core,
            ctx,
            target,
            changed_extraction,
            code_revision="test-revision",
            idempotency_key=uuid4(),
        )
    (tmp_path / "fixture.zip").write_bytes(raw + b"changed")
    core.import_fileos_snapshot(
        ctx, fileos_manifest(tmp_path, source_id="files_member_text", hour=2), uuid4()
    )
    assert core.search_current_archive_members(ctx, "archive derivative searchable") == []
    assert core.search(ctx, "archive derivative searchable")[0].evidence_id == first.evidence_id


def test_archive_member_text_publication_rechecks_current_parent_and_target(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID], tmp_path: Path
) -> None:
    store, _ = database
    ctx, _ = tenant
    ctx = datacore_context(ctx)
    core = DataCoreStore(store)
    raw, _, result = archive_fixture(core, ctx, tmp_path, source_id="files_member_text_fence")
    recorded = core.record_archive_inventory(ctx, result, ARCHIVE_PROCESSOR, uuid4())
    target = core.archive_member_target(ctx, recorded.inventory_id, result.members[0].locator)
    extraction = ExtractionResult(
        archive_member_version_id(target),
        target.member_locator,
        ExtractionStatus.EXTRACTED,
        "stale archive derivative",
        metadata={"extractor_version": "fileos-text-v1"},
    )
    (tmp_path / "fixture.zip").write_bytes(raw + b"changed")
    core.import_fileos_snapshot(
        ctx, fileos_manifest(tmp_path, source_id="files_member_text_fence", hour=2), uuid4()
    )
    with pytest.raises(Conflict, match="no longer current"):
        publish_extracted_archive_member_text(
            core,
            ctx,
            target,
            extraction,
            code_revision="test-revision",
            idempotency_key=uuid4(),
        )


def test_current_archive_document_search_is_exact_replay_safe_and_parent_fenced(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID], tmp_path: Path
) -> None:
    store, admin = database
    ctx, _ = tenant
    ctx = datacore_context(ctx)
    core = DataCoreStore(store)
    output = io.BytesIO()
    marker = "current archive document searchable proof"
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("documents/report.pdf", pdf_bytes((marker,)))
        archive.writestr("sibling.txt", b"must not enter document search")
    raw = output.getvalue()
    (tmp_path / "documents.zip").write_bytes(raw)
    manifest = fileos_manifest(tmp_path, source_id="files_archive_document_search")
    core.import_fileos_snapshot(ctx, manifest, uuid4())
    item = manifest["items"][0]
    source = source_for(
        raw,
        item["version_id"],
        item["locator"],
        item["digest"]["value"],
        item["media_type"],
    )
    inventory = inventory_archive(raw, source)
    recorded = core.record_archive_inventory(ctx, inventory, ARCHIVE_PROCESSOR, uuid4())
    target = core.archive_document_member_target(ctx, recorded.inventory_id, "documents/report.pdf")
    processor = "sandbox-fileos-document-v1-" + "b" * 64
    first = core.publish_archive_member_document(
        ctx,
        target,
        marker,
        processor,
        "pdf",
        "archive-document-search-test-v1",
        uuid4(),
    )
    replay = core.publish_archive_member_document(
        ctx,
        target,
        marker,
        processor,
        "pdf",
        "archive-document-search-test-v1",
        uuid4(),
    )

    assert first.changed is True and replay == replace(first, changed=False)
    assert core.search_current_archive_members(ctx, marker) == []
    assert core.search_current_fileos(ctx, marker) == []
    current = core.search_current_archive_documents(ctx, marker)
    assert [hit.evidence_id for hit in current] == [first.evidence_id]
    assert current[0].locator.startswith("archive-member/archiveitem_")
    assert target.member_locator not in current[0].locator
    assert core.search(ctx, marker)[0].evidence_id == first.evidence_id
    with pytest.raises(ValueError, match="invalid current archive-document search"):
        core.search_current_archive_documents(ctx, " ")
    with pytest.raises(ValueError, match="invalid current archive-document search"):
        core.search_current_archive_documents(ctx, marker, limit=21)

    other_tenant, other_actor = uuid4(), uuid4()
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO tenants(id,name) VALUES (%s,'Archive document other')", (other_tenant,)
        )
        conn.execute(
            "INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES (%s,%s,'owner')",
            (other_tenant, other_actor),
        )
    other = replace(ctx, tenant_id=other_tenant, actor_id=other_actor, request_id=uuid4())
    assert core.search_current_archive_documents(other, marker) == []

    (tmp_path / "documents.zip").write_bytes(raw + b"changed")
    core.import_fileos_snapshot(
        ctx,
        fileos_manifest(tmp_path, source_id="files_archive_document_search", hour=2),
        uuid4(),
    )
    assert core.search_current_archive_documents(ctx, marker) == []
    assert core.search(ctx, marker)[0].evidence_id == first.evidence_id


@pytest.mark.parametrize(
    ("suffix", "image_format"),
    [
        (".jpg", "jpeg"),
        (".jpeg", "jpeg"),
        (".png", "png"),
        (".tif", "tiff"),
        (".tiff", "tiff"),
        (".bmp", "bmp"),
        (".gif", "gif"),
        (".webp", "webp"),
    ],
)
def test_current_archive_image_search_receipt_suffix_mapping(
    database: tuple[Store, str],
    tenant: tuple[TenantContext, UUID],
    tmp_path: Path,
    suffix: str,
    image_format: str,
) -> None:
    """Exercise every permitted receipt suffix; worker image bytes have separate parity tests."""
    store, _ = database
    ctx, _ = tenant
    ctx = datacore_context(ctx)
    core = DataCoreStore(store)
    _, target = archive_image_fixture(
        core,
        ctx,
        tmp_path,
        source_id="files_archive_image_suffix",
        image_suffix=suffix,
    )
    marker = "archive suffix mapping proof " + image_format
    published = core.publish_archive_member_image_ocr(
        ctx,
        target,
        marker,
        "sandbox-fileos-image-ocr-v1-" + "c" * 64,
        image_format,
        image_format,
        30,
        20,
        "RGB",
        1,
        False,
        "archive-image-suffix-test-v1",
        uuid4(),
    )
    hits = core.search_current_archive_images(ctx, marker)
    assert [hit.evidence_id for hit in hits] == [published.evidence_id]


def test_archive_member_image_ocr_publication_is_exact_replay_safe_and_provenanced(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID], tmp_path: Path
) -> None:
    store, _ = database
    ctx, _ = tenant
    ctx = datacore_context(ctx)
    core = DataCoreStore(store)
    _, target = archive_image_fixture(core, ctx, tmp_path, source_id="files_archive_image_publish")
    processor = "sandbox-fileos-image-ocr-v1-" + "b" * 64
    marker = "archive image OCR retained proof 4471"
    key = uuid4()
    arguments = (
        ctx,
        target,
        marker,
        processor,
        "png",
        "png",
        1200,
        260,
        "RGB",
        1,
        False,
        "archive-image-test-v1",
    )

    assert core.search_current_archive_images(ctx, marker) == []
    with pytest.raises(ValueError, match="invalid archive member image OCR publication"):
        core.publish_archive_member_image_ocr(
            ctx,
            target,
            marker,
            processor,
            "jpeg",
            "jpeg",
            1200,
            260,
            "RGB",
            1,
            False,
            "archive-image-test-v1",
            uuid4(),
        )
    assert core.search_current_archive_images(ctx, marker) == []

    first = core.publish_archive_member_image_ocr(*arguments, key)
    same_key = core.publish_archive_member_image_ocr(*arguments, key)
    equivalent_key = core.publish_archive_member_image_ocr(*arguments, uuid4())
    alternate_processor = core.publish_archive_member_image_ocr(
        ctx,
        target,
        "alternate processor archive OCR proof",
        "sandbox-fileos-image-ocr-v1-" + "f" * 64,
        "png",
        "png",
        1200,
        260,
        "RGB",
        1,
        True,
        "archive-image-test-v2",
        uuid4(),
    )

    assert first.changed is True
    assert same_key == equivalent_key == replace(first, changed=False)
    assert alternate_processor.changed is True
    assert alternate_processor.version_id == first.version_id
    assert alternate_processor.document_id != first.document_id
    assert core.search(ctx, marker)[0].evidence_id == first.evidence_id
    assert core.search_current_archive_members(ctx, marker) == []
    assert core.search_current_archive_documents(ctx, marker) == []
    assert core.search_current_fileos(ctx, marker) == []
    current_ocr = core.search_current_archive_images(ctx, marker)
    assert [hit.evidence_id for hit in current_ocr] == [first.evidence_id]
    assert current_ocr[0].locator.startswith("archive-member/archiveitem_")
    assert target.member_locator not in current_ocr[0].locator
    token = secrets.token_urlsafe(40)
    api = TestClient(
        create_app(
            store,
            TokenRegistry(
                [
                    Credential(
                        token_sha256=hashlib.sha256(token.encode()).hexdigest(),
                        tenant_id=ctx.tenant_id,
                        actor_id=ctx.actor_id,
                        scopes={"brain.search", "knowledge.search"},
                        expires_at=datetime.now(UTC) + timedelta(minutes=5),
                        client_kind="human",
                    )
                ]
            ),
        )
    )
    response = api.post(
        "/v1/brain/current-search",
        json={"query": marker, "archive_image_limit": 3},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    grouped = response.json()
    assert grouped["layers"]["archive_images"][0]["evidence_id"] == first.evidence_id
    assert grouped["limits"]["archive_images"] == 3
    assert grouped["coverage"]["archive_images"] == (
        "explicitly_published_current_archive_images_only"
    )
    assert target.member_locator not in response.text
    assert processor not in response.text
    assert not {"width", "height", "image_processor", "member_locator"} & set(
        grouped["layers"]["archive_images"][0]
    )
    assert (
        core.search_current_archive_images(ctx, "alternate processor archive OCR proof")[
            0
        ].evidence_id
        == alternate_processor.evidence_id
    )
    with pytest.raises(ValueError, match="invalid current archive-image search"):
        core.search_current_archive_images(ctx, " ")
    with pytest.raises(ValueError, match="invalid current archive-image search"):
        core.search_current_archive_images(ctx, marker, limit=21)
    with store.transaction(ctx) as conn:
        receipt = conn.execute(
            "SELECT image_processor,image_format,detected_format,width,height,mode,"
            "frame_count,truncated,chunk_count FROM brain_archive_member_image_receipts "
            "WHERE idempotency_key=%s",
            (key,),
        ).fetchone()
        assert receipt == {
            "image_processor": processor,
            "image_format": "png",
            "detected_format": "png",
            "width": 1200,
            "height": 260,
            "mode": "RGB",
            "frame_count": 1,
            "truncated": False,
            "chunk_count": 1,
        }
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM brain_archive_member_image_receipts "
                "WHERE inventory_id=%s AND member_locator=%s",
                (target.inventory_id, target.member_locator),
            ).fetchone()["n"]
            == 3
        )
        provenance = conn.execute(
            "SELECT transform,transform_version,configuration_sha256 "
            "FROM brain_provenance WHERE output_id=%s",
            (first.document_id,),
        ).fetchone()
        expected_configuration = hashlib.sha256(
            json.dumps(
                {
                    "contract": "archive-member-image-ocr-v1",
                    "inventory_processor": target.inventory_processor_version,
                    "member_read_contract": "sandbox-fileos-archive-member-v1",
                    "image_contract": "sandbox-fileos-image-ocr-v1",
                    "image_policy": "bounded_image_ocr_v1",
                    "image_processor": processor,
                    "image_format": "png",
                    "detected_format": "png",
                    "width": 1200,
                    "height": 260,
                    "mode": "RGB",
                    "frame_count": 1,
                    "truncated": False,
                    "chunk_characters": 1000,
                },
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
        assert provenance == {
            "transform": "archive_member_image_ocr",
            "transform_version": processor,
            "configuration_sha256": expected_configuration,
        }
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM brain_provenance_inputs p JOIN brain_provenance v "
                "ON v.tenant_id=p.tenant_id AND v.id=p.provenance_id "
                "WHERE v.output_id=%s",
                (first.document_id,),
            ).fetchone()["n"]
            == 2
        )
        evidence = conn.execute(
            "SELECT storage,retained FROM brain_evidence WHERE id=%s",
            (first.evidence_id,),
        ).fetchone()
        assert evidence == {"storage": "source_bound", "retained": False}
        assert (
            conn.execute(
                "SELECT body FROM brain_normalized_documents WHERE id=%s",
                (first.document_id,),
            ).fetchone()["body"]
            == marker
        )

    with pytest.raises(Conflict, match="idempotency key"):
        core.publish_archive_member_image_ocr(
            ctx,
            target,
            marker + " changed",
            processor,
            "png",
            "png",
            1200,
            260,
            "RGB",
            1,
            False,
            "archive-image-test-v1",
            key,
        )
    with pytest.raises(psycopg.errors.InsufficientPrivilege), store.transaction(ctx) as conn:
        conn.execute(
            "UPDATE brain_archive_member_image_receipts SET width=1 WHERE idempotency_key=%s",
            (key,),
        )


def test_archive_member_image_ocr_publication_converges_and_rechecks_current_parent(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID], tmp_path: Path
) -> None:
    store, admin = database
    ctx, _ = tenant
    ctx = datacore_context(ctx)
    core = DataCoreStore(store)
    raw, target = archive_image_fixture(core, ctx, tmp_path, source_id="files_archive_image_fence")
    processor = "sandbox-fileos-image-ocr-v1-" + "c" * 64

    def publish(key: UUID):
        return core.publish_archive_member_image_ocr(
            ctx,
            target,
            "concurrent archive image proof",
            processor,
            "png",
            "png",
            40,
            30,
            "RGB",
            1,
            False,
            "archive-image-concurrency-v1",
            key,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(publish, (uuid4(), uuid4())))
    assert sorted(result.changed for result in results) == [False, True]
    assert len({result.document_id for result in results}) == 1
    assert len(core.search_current_archive_images(ctx, "concurrent archive image proof")) == 1

    other_tenant, other_actor = uuid4(), uuid4()
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO tenants(id,name) VALUES (%s,'Archive image other')", (other_tenant,)
        )
        conn.execute(
            "INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES (%s,%s,'owner')",
            (other_tenant, other_actor),
        )
    other = replace(ctx, tenant_id=other_tenant, actor_id=other_actor, request_id=uuid4())
    assert core.search_current_archive_images(other, "concurrent archive image proof") == []
    with pytest.raises(NotFound):
        core.publish_archive_member_image_ocr(
            other,
            target,
            "cross tenant must fail",
            "sandbox-fileos-image-ocr-v1-" + "d" * 64,
            "png",
            "png",
            40,
            30,
            "RGB",
            1,
            False,
            "archive-image-cross-tenant-v1",
            uuid4(),
        )

    (tmp_path / "fixture.zip").write_bytes(raw + b"changed")
    core.import_fileos_snapshot(
        ctx,
        fileos_manifest(tmp_path, source_id="files_archive_image_fence", hour=2),
        uuid4(),
    )
    assert core.search_current_archive_images(ctx, "concurrent archive image proof") == []
    assert (
        core.search(ctx, "concurrent archive image proof")[0].evidence_id == results[0].evidence_id
    )
    with pytest.raises(Conflict, match="no longer current"):
        publish(uuid4())
    with pytest.raises(Conflict, match="no longer current"):
        core.publish_archive_member_image_ocr(
            ctx,
            target,
            "stale archive image proof",
            "sandbox-fileos-image-ocr-v1-" + "e" * 64,
            "png",
            "png",
            40,
            30,
            "RGB",
            1,
            False,
            "archive-image-stale-v1",
            uuid4(),
        )


def test_private_archive_image_command_publishes_replays_and_refuses_stale_parent(
    database: tuple[Store, str],
    tenant: tuple[TenantContext, UUID],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _ = database
    tenant_ctx, _ = tenant
    ctx = datacore_context(tenant_ctx)
    root = tmp_path / "source"
    root.mkdir()
    core = DataCoreStore(store)
    raw, target = archive_image_fixture(
        core, ctx, root, source_id="files_archive_image_private_command"
    )
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    token = secrets.token_urlsafe(40)
    token_file = state / "token"
    token_file.write_bytes(token.encode())
    token_file.chmod(0o600)
    credentials_file = state / "credentials.json"
    credentials_file.write_text(
        json.dumps(
            [
                {
                    "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
                    "tenant_id": str(ctx.tenant_id),
                    "actor_id": str(ctx.actor_id),
                    "scopes": ["brain.source.ingest", "brain.document.publish"],
                    "client_kind": "worker",
                    "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                }
            ]
        )
    )
    credentials_file.chmod(0o600)
    config_file = state / "archive-image.json"
    config_file.write_text(
        json.dumps(
            {
                "version": 1,
                "root": str(root),
                "archive_image_id": "sha256:" + "a" * 64,
                "image_ocr_image_id": "sha256:" + "b" * 64,
                "docker_binary": "/usr/bin/false",
                "credentials_file": str(credentials_file),
                "token_file": str(token_file),
                "code_revision": "archive-image-command-test-v1",
            }
        )
    )
    config_file.chmod(0o600)

    class LocalArchiveProcessor:
        def __init__(self, image_id: str, *, docker_binary: Path) -> None:
            assert image_id == "sha256:" + "a" * 64
            assert docker_binary == Path("/usr/bin/false")

        def read(self, archive_raw: bytes, *, source: Any, target: Any) -> Any:
            return decode_member_result(
                read_archive_member(encode_member_request(archive_raw, source, target)),
                source,
                target,
            )

    marker = "private archive image OCR proof 4881"

    class LocalImageProcessor:
        processor_version = IMAGE_OCR_CONTRACT + "-" + "b" * 64

        def __init__(self, image_id: str, *, docker_binary: Path) -> None:
            assert image_id == "sha256:" + "b" * 64
            assert docker_binary == Path("/usr/bin/false")

        def extract(self, image_raw: bytes, *, suffix: str, sha256: str, format: str) -> Any:
            source = image_source_for(image_raw, suffix=suffix, sha256=sha256, format=format)
            return ImageOcrResult(
                source=source,
                status="extracted",
                reason="bounded_image_ocr_v1",
                detected_format="png",
                width=40,
                height=30,
                mode="RGB",
                frame_count=1,
                text=marker,
            )

    monkeypatch.setattr(archive_controller, "Store", Mock(return_value=store))
    monkeypatch.setattr(archive_controller, "DockerArchiveMemberProcessor", LocalArchiveProcessor)
    monkeypatch.setattr(archive_controller, "DockerImageOcrProcessor", LocalImageProcessor)
    key = uuid4()
    arguments = (config_file, store.dsn, target.inventory_id, target.member_locator, key)
    checked = archive_controller.run_archive_member_image_ocr_controller(*arguments, check=True)
    assert checked["execution_verified"] is False and checked["data_effects"] is False
    with store.transaction(ctx) as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM brain_archive_member_image_receipts "
                "WHERE inventory_id=%s",
                (target.inventory_id,),
            ).fetchone()["n"]
            == 0
        )

    first = archive_controller.run_archive_member_image_ocr_controller(*arguments)
    replay = archive_controller.run_archive_member_image_ocr_controller(*arguments)
    assert first["changed"] is True and replay == {**first, "changed": False}
    assert first["operation"] == "archive_member_image_ocr"
    assert first["chunks"] == 1 and first["source_effects"] is False
    assert target.member_locator not in json.dumps(first)
    assert marker not in json.dumps(first)
    assert (root / "fixture.zip").read_bytes() == raw
    with store.transaction(ctx) as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM brain_archive_member_image_receipts "
                "WHERE inventory_id=%s",
                (target.inventory_id,),
            ).fetchone()["n"]
            == 1
        )
        assert (
            conn.execute(
                "SELECT body FROM brain_normalized_documents WHERE id=%s",
                (first["document_id"],),
            ).fetchone()["body"]
            == marker
        )

    (root / "fixture.zip").write_bytes(raw + b"changed")
    core.import_fileos_snapshot(
        ctx,
        fileos_manifest(root, source_id="files_archive_image_private_command", hour=2),
        uuid4(),
    )
    with pytest.raises(archive_controller.ArchiveMemberControllerError):
        archive_controller.run_archive_member_image_ocr_controller(*arguments)
    with store.transaction(ctx) as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM brain_archive_member_image_receipts "
                "WHERE inventory_id=%s",
                (target.inventory_id,),
            ).fetchone()["n"]
            == 1
        )
    assert core.search(ctx, marker)[0].evidence_id == first["evidence_id"]


def test_archive_member_text_plan_is_current_paged_eligible_and_replay_deduplicated(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID], tmp_path: Path
) -> None:
    store, _ = database
    ctx, _ = tenant
    ctx = datacore_context(ctx)
    core = DataCoreStore(store)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("a.txt", b"first preview member")
        archive.writestr("image.bin", b"\x00\x01")
        archive.writestr("large.csv", random.Random(42).randbytes(1_048_576 + 1))
        archive.writestr("nested/b.md", b"second preview member")
    raw = output.getvalue()
    path = tmp_path / "preview.zip"
    path.write_bytes(raw)
    manifest = fileos_manifest(tmp_path, source_id="files_archive_preview")
    core.import_fileos_snapshot(ctx, manifest, uuid4())
    item = manifest["items"][0]
    source = source_for(
        raw,
        item["version_id"],
        item["locator"],
        item["digest"]["value"],
        item["media_type"],
    )
    inventory = inventory_archive(raw, source)
    recorded = core.record_archive_inventory(ctx, inventory, ARCHIVE_PROCESSOR, uuid4())

    first = core.archive_member_text_plan(ctx, recorded.inventory_id, limit=1)
    assert first["eligible_members"] == 2
    assert first["next_cursor"] == first["results"][0]["ordinal"]
    assert first["results"][0]["member_locator"] == "a.txt"
    assert first["results"][0]["already_published"] is False
    assert first["untrusted_metadata"] is True
    assert first["source_effects"] is False and first["data_effects"] is False
    second = core.archive_member_text_plan(
        ctx, recorded.inventory_id, after=first["next_cursor"], limit=1
    )
    assert second["next_cursor"] is None
    assert [row["member_locator"] for row in second["results"]] == ["nested/b.md"]
    assert not {"image.bin", "large.csv"} & {
        row["member_locator"] for row in first["results"] + second["results"]
    }
    with pytest.raises(NotFound):
        core.archive_member_text_plan(ctx, recorded.inventory_id, after=1999)

    target = core.archive_member_target(ctx, recorded.inventory_id, "a.txt")
    extraction = ExtractionResult(
        archive_member_version_id(target),
        target.member_locator,
        ExtractionStatus.EXTRACTED,
        "first preview member",
        metadata={"extractor_version": "fileos-text-v1"},
    )
    key = uuid4()
    publish_extracted_archive_member_text(
        core, ctx, target, extraction, code_revision="preview-v1", idempotency_key=key
    )
    publish_extracted_archive_member_text(
        core, ctx, target, extraction, code_revision="preview-v1", idempotency_key=key
    )
    replayed = core.archive_member_text_plan(ctx, recorded.inventory_id, limit=2)
    assert len(replayed["results"]) == 2
    assert replayed["results"][0]["already_published"] is True

    path.write_bytes(raw + b"changed")
    core.import_fileos_snapshot(
        ctx, fileos_manifest(tmp_path, source_id="files_archive_preview", hour=2), uuid4()
    )
    with pytest.raises(NotFound):
        core.archive_member_text_plan(ctx, recorded.inventory_id)


def test_archive_document_plan_is_exact_paged_replay_safe_and_current(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID], tmp_path: Path
) -> None:
    store, admin = database
    ctx, _ = tenant
    ctx = datacore_context(ctx)
    core = DataCoreStore(store)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("a.pdf", pdf_bytes(("document preview proof",)))
        archive.writestr("skip.txt", b"not a document candidate")
        archive.writestr("b.docx", docx_bytes("word preview proof"))
        archive.writestr("c.xlsx", xlsx_bytes("Preview", 1, 1, "sheetpreviewproof"))
    raw = output.getvalue()
    path = tmp_path / "document-preview.zip"
    path.write_bytes(raw)
    manifest = fileos_manifest(tmp_path, source_id="files_archive_document_preview")
    core.import_fileos_snapshot(ctx, manifest, uuid4())
    item = manifest["items"][0]
    source = source_for(
        raw,
        item["version_id"],
        item["locator"],
        item["digest"]["value"],
        item["media_type"],
    )
    recorded = core.record_archive_inventory(
        ctx, inventory_archive(raw, source), ARCHIVE_PROCESSOR, uuid4()
    )

    first = core.archive_member_document_plan(ctx, recorded.inventory_id, limit=1)
    assert first["eligible_members"] == 3
    assert first["results"][0]["member_locator"] == "a.pdf"
    assert first["results"][0]["document_format"] == "pdf"
    assert first["results"][0]["already_published"] is False
    assert first["next_cursor"] == first["results"][0]["ordinal"]
    assert first["worker_effects"] is False and first["data_effects"] is False
    second = core.archive_member_document_plan(
        ctx, recorded.inventory_id, after=first["next_cursor"], limit=2
    )
    assert [row["document_format"] for row in second["results"]] == ["docx", "xlsx"]
    assert second["next_cursor"] is None
    with pytest.raises(NotFound):
        core.archive_member_document_plan(ctx, recorded.inventory_id, after=1)

    target = core.archive_document_member_target(ctx, recorded.inventory_id, "a.pdf")
    core.publish_archive_member_document(
        ctx,
        target,
        "document preview proof",
        "sandbox-fileos-document-v1-" + "c" * 64,
        "pdf",
        "document-preview-test-v1",
        uuid4(),
    )
    replayed = core.archive_member_document_plan(ctx, recorded.inventory_id, limit=3)
    assert len(replayed["results"]) == 3
    assert replayed["results"][0]["already_published"] is True

    other_tenant, other_actor = uuid4(), uuid4()
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO tenants(id,name) VALUES (%s,'Document preview other')", (other_tenant,)
        )
        conn.execute(
            "INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES (%s,%s,'owner')",
            (other_tenant, other_actor),
        )
    other = replace(ctx, tenant_id=other_tenant, actor_id=other_actor, request_id=uuid4())
    with pytest.raises(NotFound):
        core.archive_member_document_plan(other, recorded.inventory_id)

    path.write_bytes(raw + b"changed")
    core.import_fileos_snapshot(
        ctx,
        fileos_manifest(tmp_path, source_id="files_archive_document_preview", hour=2),
        uuid4(),
    )
    with pytest.raises(NotFound):
        core.archive_member_document_plan(ctx, recorded.inventory_id)


def test_fileos_adapter_isolates_sibling_failure_and_publishes_searchable_text(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID], tmp_path: Path
) -> None:
    store, admin = database
    ctx, _ = tenant
    ctx = datacore_context(ctx)
    good = tmp_path / "good.txt"
    changed = tmp_path / "changed.txt"
    unsupported = tmp_path / "image.bin"
    good.write_text("MasterBrain searchable source truth", encoding="utf-8")
    changed.write_text("before", encoding="utf-8")
    unsupported.write_bytes(b"\x00\x01")
    manifest = fileos_manifest(tmp_path, source_id="files_adapter")
    changed.write_text("after", encoding="utf-8")

    core = DataCoreStore(store)
    run_id = uuid4()
    result = FileOSAdapter(core).publish_snapshot(
        ctx,
        tmp_path,
        manifest,
        run_id,
        code_revision="test-adapter-v1",
    )
    assert result.counts == {"changed": 1, "extracted": 1, "unsupported": 1}
    by_name = {entry.extraction.locator: entry for entry in result.results}
    assert by_name["good.txt"].publication is not None
    assert by_name["changed.txt"].extraction.status is ExtractionStatus.CHANGED
    assert by_name["image.bin"].extraction.status is ExtractionStatus.UNSUPPORTED
    assert core.fileos_freshness(ctx, "files_adapter") == {
        "source_id": "files_adapter",
        "status": "no_completed_run",
        "latest_complete_run": None,
        "partial_runs_included": False,
    }
    initial_coverage = next(
        row for row in core.current_coverage(ctx)["results"] if row["source_id"] == "files_adapter"
    )
    assert initial_coverage["status"] == "no_active_generation"
    assert initial_coverage["active_generation"] is None
    assert initial_coverage["latest_complete_run"] is None
    assert initial_coverage["latest_completion_is_active"] is False
    receipt = core.complete_fileos_run(
        ctx,
        manifest,
        run_id,
        outcomes=result.counts,
        item_outcomes={
            item["item_id"]: by_name[item["locator"]].extraction.status.value
            for item in manifest["items"]
        },
        published_documents=1,
        code_revision="test-adapter-v1",
        document_processor_version=None,
    )
    assert receipt.recorded is True
    assert (
        core.complete_fileos_run(
            ctx,
            manifest,
            run_id,
            outcomes=result.counts,
            item_outcomes={
                item["item_id"]: by_name[item["locator"]].extraction.status.value
                for item in manifest["items"]
            },
            published_documents=1,
            code_revision="test-adapter-v1",
            document_processor_version=None,
        ).recorded
        is False
    )
    with pytest.raises(Conflict):
        core.complete_fileos_run(
            ctx,
            manifest,
            run_id,
            outcomes={"changed": 1, "empty": 1, "unsupported": 1},
            item_outcomes={
                item["item_id"]: (
                    "empty"
                    if item["locator"] == "good.txt"
                    else by_name[item["locator"]].extraction.status.value
                )
                for item in manifest["items"]
            },
            published_documents=0,
            code_revision="test-adapter-v1",
            document_processor_version=None,
        )
    assert core.fileos_inventory(ctx, "files_adapter") | {"completed_at": None} == {
        "source_id": "files_adapter",
        "status": "complete",
        "run_id": run_id,
        "observed_at": datetime(2026, 9, 22, 1, tzinfo=UTC),
        "completed_at": None,
        "present_items": 3,
        "newly_absent_items": 0,
        "absent_evidence_retained": True,
        "search_visibility_changed": False,
    }
    preview_page_one = core.fileos_rebuild_preview(ctx, "files_adapter", limit=2)
    assert preview_page_one["run_id"] == run_id
    assert preview_page_one["total_items"] == 3
    assert preview_page_one["next_cursor"] is not None
    preview_page_two = core.fileos_rebuild_preview(
        ctx,
        "files_adapter",
        after=preview_page_one["next_cursor"],
        limit=2,
    )
    preview_results = preview_page_one["results"] + preview_page_two["results"]
    assert sorted(item["disposition"] for item in preview_results) == [
        "source_reprocess_required",
        "source_reprocess_required",
        "verified",
    ]
    assert all("locator" not in item and "body" not in item for item in preview_results)
    assert preview_page_two["next_cursor"] is None
    assert preview_page_two["source_effects"] is False
    assert preview_page_two["data_effects"] is False
    with pytest.raises(NotFound):
        core.fileos_rebuild_preview(ctx, "files_adapter", after="item_missing")
    first_generation = core.build_fileos_index_generation(
        ctx,
        "files_adapter",
        run_id,
        code_revision="test-index-v1",
    )
    assert first_generation.recorded is True
    assert first_generation.item_count == 3
    assert first_generation.document_count == 1
    assert first_generation.chunk_count == 1
    assert (
        core.build_fileos_index_generation(
            ctx,
            "files_adapter",
            run_id,
            code_revision="test-index-v1",
        ).recorded
        is False
    )
    revised_generation = core.build_fileos_index_generation(
        ctx,
        "files_adapter",
        run_id,
        code_revision="test-index-v2",
    )
    assert revised_generation.recorded is True
    assert revised_generation.generation_id != first_generation.generation_id
    assert revised_generation.plan_sha256 != first_generation.plan_sha256
    first_activation_key = uuid4()
    first_activation = core.activate_fileos_index_generation(
        ctx,
        "files_adapter",
        first_generation.generation_id,
        first_activation_key,
    )
    assert first_activation.recorded is True
    assert first_activation.previous_generation_id is None
    assert (
        core.activate_fileos_index_generation(
            ctx,
            "files_adapter",
            first_generation.generation_id,
            first_activation_key,
        ).recorded
        is False
    )
    assert (
        core.fileos_index_status(ctx, "files_adapter")["active_generation"]["generation_id"]
        == first_generation.generation_id
    )
    active_first_hits = core.search_fileos_active(ctx, "files_adapter", "searchable source")
    existing_first_hits = core.search(ctx, "searchable source")
    assert len(active_first_hits) == 1
    assert [
        (hit.chunk_id, hit.document_id, hit.evidence_id, hit.source_id, hit.locator)
        for hit in active_first_hits
    ] == [
        (hit.chunk_id, hit.document_id, hit.evidence_id, hit.source_id, hit.locator)
        for hit in existing_first_hits
    ]
    assert core.search_fileos_active(ctx, "files_adapter", "after") == []

    unsupported.unlink()
    next_manifest = fileos_manifest(tmp_path, source_id="files_adapter", hour=2)
    next_run_id = uuid4()
    next_result = FileOSAdapter(core).publish_snapshot(
        ctx,
        tmp_path,
        next_manifest,
        next_run_id,
        code_revision="test-adapter-v1",
    )
    next_by_version = {
        entry.extraction.version_id: entry.extraction.status.value for entry in next_result.results
    }
    core.complete_fileos_run(
        ctx,
        next_manifest,
        next_run_id,
        outcomes=next_result.counts,
        item_outcomes={
            item["item_id"]: next_by_version[item["version_id"]] for item in next_manifest["items"]
        },
        published_documents=2,
        code_revision="test-adapter-v1",
        document_processor_version=None,
    )
    inventory = core.fileos_inventory(ctx, "files_adapter")
    assert inventory["run_id"] == next_run_id
    assert inventory["present_items"] == 2
    assert inventory["newly_absent_items"] == 1
    assert inventory["absent_evidence_retained"] is True
    second_generation = core.build_fileos_index_generation(
        ctx,
        "files_adapter",
        next_run_id,
        code_revision="test-index-v1",
    )
    assert second_generation.recorded is True
    assert second_generation.item_count == 2
    assert second_generation.document_count == 2
    second_activation = core.activate_fileos_index_generation(
        ctx,
        "files_adapter",
        second_generation.generation_id,
        uuid4(),
    )
    assert second_activation.previous_generation_id == first_generation.generation_id
    for query in (
        "MasterBrain searchable",
        "source truth",
        "after",
        "term-not-present-anywhere",
    ):
        active_identity = [
            (hit.chunk_id, hit.document_id, hit.evidence_id, hit.source_id, hit.locator)
            for hit in core.search_fileos_active(ctx, "files_adapter", query)
        ]
        existing_identity = [
            (hit.chunk_id, hit.document_id, hit.evidence_id, hit.source_id, hit.locator)
            for hit in core.search(ctx, query)
            if hit.source_id == "files_adapter"
        ]
        assert active_identity == existing_identity
        assert active_identity == [
            (hit.chunk_id, hit.document_id, hit.evidence_id, hit.source_id, hit.locator)
            for hit in core.search_current_fileos(ctx, query)
        ]
    after_hits = core.search_fileos_active(ctx, "files_adapter", "after")
    assert len(after_hits) == 1 and after_hits[0].locator == "changed.txt"
    rollback = core.activate_fileos_index_generation(
        ctx,
        "files_adapter",
        first_generation.generation_id,
        uuid4(),
    )
    assert rollback.previous_generation_id == second_generation.generation_id
    assert core.search_fileos_active(ctx, "files_adapter", "after") == []
    assert core.search_current_fileos(ctx, "after") == []
    reactivate = core.activate_fileos_index_generation(
        ctx,
        "files_adapter",
        second_generation.generation_id,
        uuid4(),
    )
    assert reactivate.previous_generation_id == first_generation.generation_id
    with pytest.raises(Conflict, match="key reused"):
        core.activate_fileos_index_generation(
            ctx,
            "files_adapter",
            second_generation.generation_id,
            first_activation_key,
        )
    other_root = tmp_path / "other-source"
    other_root.mkdir()
    (other_root / "other.txt").write_text("MasterBrain searchable constellation", encoding="utf-8")
    other_manifest = fileos_manifest(other_root, source_id="files_other", hour=3)
    other_run_id = uuid4()
    other_result = FileOSAdapter(core).publish_snapshot(
        ctx,
        other_root,
        other_manifest,
        other_run_id,
        code_revision="test-adapter-v1",
    )
    other_by_version = {
        item.extraction.version_id: item.extraction.status.value for item in other_result.results
    }
    core.complete_fileos_run(
        ctx,
        other_manifest,
        other_run_id,
        outcomes=other_result.counts,
        item_outcomes={
            item["item_id"]: other_by_version[item["version_id"]]
            for item in other_manifest["items"]
        },
        published_documents=1,
        code_revision="test-adapter-v1",
        document_processor_version=None,
    )
    other_generation = core.build_fileos_index_generation(
        ctx,
        "files_other",
        other_run_id,
        code_revision="test-index-v1",
    )
    core.activate_fileos_index_generation(
        ctx, "files_other", other_generation.generation_id, uuid4()
    )
    cross_source_hits = core.search_current_fileos(ctx, "MasterBrain searchable")
    assert {hit.source_id for hit in cross_source_hits} == {"files_adapter", "files_other"}
    assert len(core.search_current_fileos(ctx, "MasterBrain searchable", limit=1)) == 1
    stale_run_id = uuid4()
    core.import_fileos_snapshot(ctx, manifest, stale_run_id)
    with pytest.raises(Conflict, match="not newer"):
        core.complete_fileos_run(
            ctx,
            manifest,
            stale_run_id,
            outcomes=result.counts,
            item_outcomes={
                item["item_id"]: by_name[item["locator"]].extraction.status.value
                for item in manifest["items"]
            },
            published_documents=1,
            code_revision="test-adapter-v1",
            document_processor_version=None,
        )
    hits = core.search(ctx, "searchable source")
    assert len(hits) == 1 and hits[0].locator == "good.txt"
    token = secrets.token_urlsafe(40)
    api = TestClient(
        create_app(
            store,
            TokenRegistry(
                [
                    Credential(
                        token_sha256=hashlib.sha256(token.encode()).hexdigest(),
                        tenant_id=ctx.tenant_id,
                        actor_id=ctx.actor_id,
                        scopes={
                            "brain.search",
                            "brain.evidence.read",
                            "brain.content.read",
                            "brain.changes.read",
                        },
                        expires_at=datetime.now(UTC) + timedelta(minutes=5),
                        client_kind="assistant",
                    )
                ]
            ),
        )
    )
    headers = {"Authorization": f"Bearer {token}"}
    searched = api.post(
        "/v1/brain/search", json={"query": "searchable source", "limit": 5}, headers=headers
    )
    assert searched.status_code == 200
    evidence_id = searched.json()["results"][0]["evidence_id"]
    evidence = api.get(f"/v1/brain/evidence/{evidence_id}", headers=headers)
    assert evidence.status_code == 200
    good_item = next(item for item in manifest["items"] if item["locator"] == "good.txt")
    assert evidence.json()["sha256"] == good_item["digest"]["value"]
    content = api.post(
        f"/v1/brain/evidence/{evidence_id}/content",
        json={"max_chars": 12},
        headers=headers,
    )
    assert content.status_code == 200
    assert content.json()["truncated"] is True and content.json()["returned_chars"] == 12
    changes = api.get("/v1/brain/changes?limit=1", headers=headers)
    assert changes.status_code == 200
    assert len(changes.json()["results"]) == 1
    assert changes.json()["next_cursor"] is not None
    freshness = api.get("/v1/brain/sources/files_adapter/freshness", headers=headers)
    assert freshness.status_code == 200
    assert freshness.json()["status"] == "complete"
    assert freshness.json()["latest_complete_run"]["run_id"] == str(next_run_id)
    assert freshness.json()["latest_complete_run"]["outcomes"] == next_result.counts
    inventory_response = api.get("/v1/brain/sources/files_adapter/inventory", headers=headers)
    assert inventory_response.status_code == 200
    assert inventory_response.json()["run_id"] == str(next_run_id)
    assert inventory_response.json()["newly_absent_items"] == 1
    preview_response = api.get(
        "/v1/brain/sources/files_adapter/rebuild-preview?limit=2", headers=headers
    )
    assert preview_response.status_code == 200
    assert preview_response.json()["run_id"] == str(next_run_id)
    assert {item["disposition"] for item in preview_response.json()["results"]} == {"verified"}
    index_response = api.get("/v1/brain/sources/files_adapter/index", headers=headers)
    assert index_response.status_code == 200
    assert (
        index_response.json()["active_generation"]["generation_id"]
        == second_generation.generation_id
    )
    active_search = api.post(
        "/v1/brain/sources/files_adapter/search",
        json={"query": "after", "limit": 5},
        headers=headers,
    )
    assert active_search.status_code == 200
    assert active_search.json()["active_generation_only"] is True
    assert active_search.json()["results"][0]["locator"] == "changed.txt"
    current_search = api.post(
        "/v1/brain/fileos-search",
        json={"query": "after", "limit": 5},
        headers=headers,
    )
    assert current_search.status_code == 200
    assert current_search.json()["visibility"] == "current_fileos_active_generations"
    assert current_search.json()["results"][0]["locator"] == "changed.txt"
    with pytest.raises(psycopg.errors.RaiseException), psycopg.connect(admin) as conn:
        conn.execute(
            "UPDATE brain_fileos_run_receipts SET outcomes='{}' WHERE tenant_id=%s",
            (ctx.tenant_id,),
        )
    with pytest.raises(psycopg.errors.RaiseException), psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO brain_index_generation_items "
            "SELECT * FROM brain_index_generation_items WHERE tenant_id=%s LIMIT 1",
            (ctx.tenant_id,),
        )
    with pytest.raises(psycopg.errors.CheckViolation), psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO brain_fileos_run_receipts(tenant_id,actor_id,run_id,source_id,"
            "observed_at,manifest_sha256,code_revision,text_extractor_version,item_count,"
            "outcomes,published_documents) VALUES (%s,%s,%s,'files_adapter',now(),%s,"
            "'invalid-test','fileos-text-v1',3,'{\"extracted\":2}'::jsonb,1)",
            (ctx.tenant_id, ctx.actor_id, uuid4(), "a" * 64),
        )


def knowledge_context(ctx: TenantContext) -> TenantContext:
    return replace(
        datacore_context(ctx),
        scopes=datacore_context(ctx).scopes
        | frozenset(
            {
                "knowledge.review",
                "knowledge.read",
                "knowledge.search",
                "knowledge.changes.read",
            }
        ),
    )


def test_knowledgecore_all_objects_conflicts_history_api_rls_and_immutability(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID], tmp_path: Path
) -> None:
    store, admin = database
    ctx, account = tenant
    ctx = knowledge_context(ctx)
    source = tmp_path / "knowledge.txt"
    source.write_text("Alex at Acme committed to renew Project Atlas in October.", encoding="utf-8")
    manifest = fileos_manifest(tmp_path, source_id="files_knowledge")
    core = DataCoreStore(store)
    run_id = uuid4()
    published = FileOSAdapter(core).publish_snapshot(
        ctx, tmp_path, manifest, run_id, code_revision="knowledge-test-v1"
    )
    evidence_id = next(
        item.publication.evidence_id for item in published.results if item.publication is not None
    )
    outcomes_by_version = {
        item.extraction.version_id: item.extraction.status.value for item in published.results
    }
    core.complete_fileos_run(
        ctx,
        manifest,
        run_id,
        outcomes=published.counts,
        item_outcomes={
            item["item_id"]: outcomes_by_version[item["version_id"]] for item in manifest["items"]
        },
        published_documents=1,
        code_revision="knowledge-test-v1",
        document_processor_version=None,
    )
    generation = core.build_fileos_index_generation(
        ctx, "files_knowledge", run_id, code_revision="knowledge-index-v1"
    )
    core.activate_fileos_index_generation(ctx, "files_knowledge", generation.generation_id, uuid4())
    store.ingest_page(
        ctx,
        account,
        None,
        "knowledge-email-page",
        [item("knowledge-email", body="Project Atlas current Email evidence")],
    )
    legacy_email = store.search(ctx, SearchRequest(query="Project Atlas current Email evidence"))[
        0
    ]["evidence_id"]
    current_email = core.bridge_current_email_version(
        ctx, legacy_email, uuid4(), code_revision="knowledge-current-email-v1"
    )
    common = {
        "evidence_ids": [evidence_id],
        "source_quote": "Alex at Acme committed to renew Project Atlas in October.",
        "confidence": 0.9,
        "observed_at": datetime(2026, 9, 22, tzinfo=UTC),
        "reviewed": True,
    }
    knowledge = KnowledgeCore(store)
    alice_key = uuid4()
    alice = EntityWrite(
        kind="entity", entity_type="person", name="Alex Example", aliases=["Alex"], **common
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        concurrent = list(pool.map(lambda _: knowledge.publish(ctx, alice, alice_key), range(2)))
    assert {result.object_id for result in concurrent} == {concurrent[0].object_id}
    assert sorted(result.changed for result in concurrent) == [False, True]
    assert knowledge.publish(ctx, alice, alice_key).changed is False
    with pytest.raises(Conflict):
        knowledge.publish(ctx, alice.model_copy(update={"name": "Different"}), alice_key)

    acme = knowledge.publish(
        ctx,
        EntityWrite(
            kind="entity",
            entity_type="organization",
            name="Acme Holdings",
            aliases=["Acme"],
            **common,
        ),
        uuid4(),
    )
    relationship = knowledge.publish(
        ctx,
        RelationshipWrite(
            kind="relationship",
            subject_entity_id=concurrent[0].object_id,
            predicate="affiliated_with",
            object_entity_id=acme.object_id,
            **common,
        ),
        uuid4(),
    )
    first_claim = knowledge.publish(
        ctx,
        ClaimWrite(
            kind="claim",
            subject_entity_id=concurrent[0].object_id,
            predicate="renewal_month",
            value="September",
            assertion_status="disputed",
            **common,
        ),
        uuid4(),
    )
    second_claim = knowledge.publish(
        ctx,
        ClaimWrite(
            kind="claim",
            subject_entity_id=concurrent[0].object_id,
            predicate="renewal_month",
            value="October",
            supersedes_id=first_claim.object_id,
            **common,
        ),
        uuid4(),
    )
    project = knowledge.publish(
        ctx,
        ProjectWrite(
            kind="project",
            title="Project Atlas",
            description="Renewal program",
            state="active",
            **common,
        ),
        uuid4(),
    )
    event = knowledge.publish(
        ctx,
        EventWrite(
            kind="event",
            event_type="renewal_review",
            title="Atlas renewal review",
            description="Review the renewal evidence",
            starts_at=datetime(2026, 10, 1, tzinfo=UTC),
            valid_from=datetime(2026, 9, 22, tzinfo=UTC),
            project_id=project.object_id,
            **common,
        ),
        uuid4(),
    )
    commitment = knowledge.publish(
        ctx,
        CommitmentWrite(
            kind="commitment",
            description="Alex will submit the Atlas renewal package",
            state="open",
            owner_entity_id=concurrent[0].object_id,
            counterparty_entity_id=acme.object_id,
            project_id=project.object_id,
            due_at=datetime(2026, 10, 15, tzinfo=UTC),
            valid_from=datetime(2026, 9, 22, tzinfo=UTC),
            **common,
        ),
        uuid4(),
    )
    correction = knowledge.publish(
        ctx,
        CorrectionWrite(
            kind="correction",
            target_kind="claim",
            target_id=first_claim.object_id,
            replacement_id=second_claim.object_id,
            reason="Later reviewed evidence corrects the month.",
            evidence_ids=[evidence_id],
            source_quote=common["source_quote"],
            observed_at=common["observed_at"],
            reviewed=True,
        ),
        uuid4(),
    )
    assert {
        relationship.object_kind,
        event.object_kind,
        commitment.object_kind,
        correction.object_kind,
    } == {"relationship", "event", "commitment", "correction"}
    with store.transaction(ctx) as conn:
        claims = conn.execute(
            "SELECT id,value,assertion_status,supersedes_id FROM knowledge_claims "
            "ORDER BY recorded_at,id"
        ).fetchall()
        assert len(claims) == 2
        assert {row["value"] for row in claims} == {"September", "October"}
        assert next(row for row in claims if row["value"] == "October")["supersedes_id"] == (
            first_claim.object_id
        )

    hits = knowledge.search(ctx, "October", kinds=["claim"])
    assert len(hits) == 1 and hits[0].object_id == second_claim.object_id
    loaded = knowledge.get(ctx, "commitment", commitment.object_id)
    assert loaded["description"].startswith("Alex will submit")
    assert loaded["valid_from"] == datetime(2026, 9, 22, tzinfo=UTC)
    assert loaded["evidence"][0]["evidence_id"] == evidence_id
    page = knowledge.changes(ctx, limit=2)
    assert len(page["results"]) == 2 and page["next_cursor"] is not None
    second_page = knowledge.changes(ctx, after=page["next_cursor"], limit=50)
    assert second_page["results"]

    with pytest.raises(psycopg.errors.InsufficientPrivilege), store.transaction(ctx) as conn:
        conn.execute(
            "UPDATE knowledge_claims SET value='silently changed' WHERE id=%s",
            (second_claim.object_id,),
        )

    other_tenant, other_actor = uuid4(), uuid4()
    with psycopg.connect(admin) as conn:
        conn.execute("INSERT INTO tenants(id,name) VALUES (%s,'Knowledge other')", (other_tenant,))
        conn.execute(
            "INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES (%s,%s,'owner')",
            (other_tenant, other_actor),
        )
    other = replace(ctx, tenant_id=other_tenant, actor_id=other_actor, request_id=uuid4())
    assert knowledge.search(other, "October") == []
    assert core.current_coverage(other)["results"] == []
    with pytest.raises(NotFound):
        knowledge.get(other, "claim", second_claim.object_id)

    token = secrets.token_urlsafe(40)
    api = TestClient(
        create_app(
            store,
            TokenRegistry(
                [
                    Credential(
                        token_sha256=hashlib.sha256(token.encode()).hexdigest(),
                        tenant_id=ctx.tenant_id,
                        actor_id=ctx.actor_id,
                        scopes={
                            "brain.search",
                            "brain.changes.read",
                            "knowledge.search",
                            "knowledge.read",
                            "knowledge.changes.read",
                            "knowledge.review",
                        },
                        expires_at=datetime.now(UTC) + timedelta(minutes=5),
                        client_kind="human",
                    )
                ]
            ),
        )
    )
    headers = {"Authorization": f"Bearer {token}"}
    searched = api.post(
        "/v1/knowledge/search",
        json={"query": "Atlas renewal", "limit": 10},
        headers=headers,
    )
    assert searched.status_code == 200 and searched.json()["results"]
    unified = api.post(
        "/v1/brain/unified-search",
        json={
            "query": "Project Atlas",
            "evidence_limit": 5,
            "knowledge_limit": 5,
            "knowledge_kinds": ["project"],
        },
        headers=headers,
    )
    assert unified.status_code == 200
    assert unified.json()["ranking"] == "within_layer_only"
    assert evidence_id in {row["evidence_id"] for row in unified.json()["layers"]["evidence"]}
    assert unified.json()["layers"]["knowledge"][0]["object_id"] == project.object_id
    current_unified = api.post(
        "/v1/brain/unified-search",
        json={
            "query": "Project Atlas",
            "evidence_visibility": "current_fileos",
            "evidence_limit": 5,
            "knowledge_limit": 5,
            "knowledge_kinds": ["project"],
        },
        headers=headers,
    )
    assert current_unified.status_code == 200
    assert current_unified.json()["evidence_visibility"] == "current_fileos_active_generations"
    assert current_unified.json()["layers"]["evidence"][0]["evidence_id"] == evidence_id
    assert current_unified.json()["layers"]["knowledge"][0]["object_id"] == project.object_id
    grouped_current = api.post(
        "/v1/brain/current-search",
        json={
            "query": "Project Atlas",
            "fileos_limit": 5,
            "archive_member_limit": 5,
            "archive_document_limit": 5,
            "email_message_limit": 5,
            "email_attachment_limit": 5,
            "email_document_limit": 5,
            "knowledge_limit": 5,
            "knowledge_kinds": ["project"],
        },
        headers=headers,
    )
    assert grouped_current.status_code == 200
    grouped = grouped_current.json()
    assert grouped["ranking"] == "within_group_only"
    assert grouped["consistency"] == "independent_layer_reads"
    assert grouped["coverage"]["complete"] is False
    assert grouped["layers"]["fileos"][0]["evidence_id"] == evidence_id
    assert grouped["layers"]["archive_members"] == []
    assert grouped["layers"]["archive_documents"] == []
    assert grouped["layers"]["archive_images"] == []
    assert grouped["layers"]["email_messages"][0]["evidence_id"] == current_email.evidence_id
    assert grouped["layers"]["email_attachments"] == []
    assert grouped["layers"]["email_documents"] == []
    assert grouped["layers"]["knowledge"][0]["object_id"] == project.object_id
    first_coverage = api.get("/v1/brain/current-coverage?limit=1", headers=headers)
    assert first_coverage.status_code == 200
    assert first_coverage.json()["complete"] is False
    assert first_coverage.json()["next_cursor"] is not None
    coverage_response = api.get("/v1/brain/current-coverage?limit=50", headers=headers)
    assert coverage_response.status_code == 200
    coverage = {row["source_id"]: row for row in coverage_response.json()["results"]}
    fileos_coverage = coverage["files_knowledge"]
    assert fileos_coverage["status"] == "search_ready"
    assert fileos_coverage["active_generation"]["generation_id"] == generation.generation_id
    assert fileos_coverage["latest_completion_is_active"] is True
    email_coverage = coverage[current_email.source_id]
    assert email_coverage["coverage"] == "explicit_bridges_only"
    assert email_coverage["current_counts"] == {
        "messages": 1,
        "attachments": 0,
        "documents": 0,
    }
    assert email_coverage["latest_current_bridge_at"]["messages"] is not None
    fetched = api.get(f"/v1/knowledge/project/{project.object_id}", headers=headers)
    assert fetched.status_code == 200 and fetched.json()["title"] == "Project Atlas"
    created = api.post(
        "/v1/knowledge/assertions",
        json={
            "assertion": {
                "kind": "entity",
                "entity_type": "artifact",
                "name": "Renewal package",
                "aliases": [],
                "evidence_ids": [evidence_id],
                "source_quote": common["source_quote"],
                "confidence": 0.9,
                "observed_at": "2026-09-22T00:00:00Z",
                "reviewed": True,
            }
        },
        headers={**headers, "Idempotency-Key": str(uuid4())},
    )
    assert created.status_code == 201 and created.json()["reviewed"] is True


def test_foreign_tenant_cannot_see_evidence(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID]
) -> None:
    store, _ = database
    ctx, account = tenant
    store.ingest_page(ctx, account, None, "s1", [item()])
    evidence_id = store.search(ctx, SearchRequest(query="Melron"))[0]["evidence_id"]
    # Missing/wrong tenant membership fails before any content access.
    with pytest.raises(AccessDenied):
        store.evidence(replace(ctx, tenant_id=uuid4()), evidence_id)
    # At the database boundary even an unconstrained SELECT is isolated.
    with psycopg.connect(store.dsn) as conn:
        assert conn.execute("SELECT count(*) FROM messages").fetchone() == (0,)
        conn.execute("SELECT set_config('email_brain.tenant_id',%s,true)", (str(uuid4()),))
        assert conn.execute("SELECT count(*) FROM message_versions").fetchone() == (0,)


def test_composite_foreign_key(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID]
) -> None:
    _, admin = database
    _, account = tenant
    other_tenant = uuid4()
    with psycopg.connect(admin) as conn:
        conn.execute("INSERT INTO tenants(id,name) VALUES (%s,'Other tenant')", (other_tenant,))
    with pytest.raises(psycopg.errors.ForeignKeyViolation), psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO sync_cursors(tenant_id,account_id,scope,cursor_kind,opaque_cursor) "
            "VALUES (%s,%s,'email','synthetic','s')",
            (other_tenant, account),
        )


def test_proposal_idempotency_and_review(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID]
) -> None:
    store, _ = database
    ctx, _ = tenant
    request = ProposalRequest(
        payload=FeaturePayload(kind="feature", title="Example", desired_outcome="A new capability"),
        reason="Owner requested",
        source="synthetic",
    )
    key = uuid4()
    first = store.propose(ctx, request, key)
    assert store.propose(ctx, request, key)["id"] == first["id"]
    with pytest.raises(Conflict):
        store.propose(ctx, request.model_copy(update={"reason": "Different"}), key)
    reviewed = store.review(
        ctx, first["id"], ReviewRequest(decision="approved", expected_version=1)
    )
    assert reviewed["version"] == 2
    with pytest.raises(Conflict):
        store.review(ctx, first["id"], ReviewRequest(decision="rejected", expected_version=1))


def test_invalid_evidence_rolls_back_proposal(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID]
) -> None:
    store, _ = database
    ctx, _ = tenant
    request = ProposalRequest(
        payload=FeaturePayload(kind="feature", title="Example", desired_outcome="A new capability"),
        reason="Owner requested",
        source="synthetic",
        evidence_ids=[uuid4()],
    )
    with pytest.raises(NotFound):
        store.propose(ctx, request, uuid4())
    assert store.proposals(ctx) == []


def test_runtime_cannot_rewrite_raw_evidence(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID]
) -> None:
    store, _ = database
    ctx, account = tenant
    store.ingest_page(ctx, account, None, "s1", [item()])
    with pytest.raises(psycopg.errors.InsufficientPrivilege), store.transaction(ctx) as conn:
        conn.execute("UPDATE raw_objects SET raw_mime='fake'")


def test_attachment_search_receipts_and_duplicates(database, tenant) -> None:
    store, _ = database
    ctx, account = tenant
    mail = EmailMessage()
    mail["Subject"] = "Synthetic files"
    mail.set_content("See files")
    for name in ("first.txt", "second.txt"):
        mail.add_attachment(
            b"SpecialAttachmentWord", maintype="text", subtype="plain", filename=name
        )
    mail.add_attachment(
        b"%PDF-synthetic", maintype="application", subtype="pdf", filename="held.pdf"
    )
    store.ingest_page(ctx, account, None, "a1", [replace(item(), raw=mail.as_bytes())])
    hits = store.search(ctx, SearchRequest(query="SpecialAttachmentWord"))
    assert len(hits) == 2 and all(hit["result_type"] == "attachment" for hit in hits)
    evidence = store.evidence(ctx, hits[0]["evidence_id"])
    assert evidence["attachment_accounting"]["total"] == 3
    assert evidence["attachment_accounting"]["unaccounted"] == 0
    assert evidence["attachment_accounting"]["ready"] is False
    assert sum(a["duplicate_of"] is not None for a in evidence["attachments"]) == 1
    assert (
        store.search(ctx, SearchRequest(query="SpecialAttachmentWord", include_attachments=False))
        == []
    )


def test_rls_after_transaction_context_reset(database, tenant) -> None:
    store, _ = database
    ctx, _ = tenant
    with psycopg.connect(store.dsn, autocommit=True) as conn:
        with conn.transaction():
            conn.execute(
                "SELECT set_config('email_brain.tenant_id',%s,true)", (str(ctx.tenant_id),)
            )
            assert conn.execute("SELECT count(*) FROM mail_accounts").fetchone() == (1,)
        assert conn.execute("SELECT count(*) FROM mail_accounts").fetchone() == (0,)


def test_concurrent_page_replays_commit_once(database, tenant) -> None:
    store, _ = database
    ctx, account = tenant
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda _: store.ingest_page(ctx, account, None, "s1", [item()]), range(2))
        )
    assert sorted(results) == [0, 1]
    assert len(store.search(ctx, SearchRequest(query="Melron"))) == 1


def test_valid_other_tenant_owner_cannot_access_content(database, tenant) -> None:
    store, admin = database
    first_ctx, account = tenant
    store.ingest_page(first_ctx, account, None, "s1", [item()])
    evidence = store.search(first_ctx, SearchRequest(query="Melron"))[0]["evidence_id"]
    other_id, other_actor = uuid4(), uuid4()
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO tenants(id,name) VALUES (%s,'Other synthetic tenant')", (other_id,)
        )
        conn.execute(
            "INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES (%s,%s,'owner')",
            (other_id, other_actor),
        )
    other = replace(first_ctx, tenant_id=other_id, actor_id=other_actor)
    assert store.search(other, SearchRequest(query="Melron")) == []
    with pytest.raises(NotFound):
        store.evidence(other, evidence)
    with pytest.raises(NotFound):
        store.ingest_page(other, account, None, "not-allowed", [item()])


def test_http_to_real_database_and_correlated_audit(database, tenant) -> None:
    store, admin = database
    ctx, account = tenant
    store.ingest_page(ctx, account, None, "s1", [item()])
    token = secrets.token_urlsafe(40)
    registry = TokenRegistry(
        [
            Credential(
                token_sha256=hashlib.sha256(token.encode()).hexdigest(),
                tenant_id=ctx.tenant_id,
                actor_id=ctx.actor_id,
                scopes=set(ctx.scopes),
                client_kind="human",
                expires_at=datetime.now(UTC) + timedelta(minutes=5),
            )
        ]
    )
    client = TestClient(create_app(store, registry))
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/").status_code == 200
    assert client.get("/readyz", headers=headers).status_code == 200
    result = client.post("/v1/search", headers=headers, json={"query": "Melron"})
    assert result.status_code == 200 and len(result.json()["results"]) == 1
    evidence_id = result.json()["results"][0]["evidence_id"]
    assert client.get(f"/v1/evidence/{evidence_id}", headers=headers).status_code == 200
    proposed = client.post(
        "/v1/proposals",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json={
            "payload": {"kind": "project", "name": "Melron"},
            "reason": "Synthetic user request",
            "source": "test",
            "evidence_ids": [evidence_id],
        },
    )
    assert proposed.status_code == 201
    review = client.post(
        f"/v1/proposals/{proposed.json()['id']}/reviews",
        headers=headers,
        json={"decision": "approved", "expected_version": 1},
    )
    assert review.status_code == 200 and review.json()["applied"] is False
    with psycopg.connect(admin) as conn:
        audit = conn.execute(
            "SELECT request_id FROM audit_events WHERE tenant_id=%s "
            "AND event_type='proposal.approved'",
            (ctx.tenant_id,),
        ).fetchone()
    assert audit is not None and str(audit[0]) == review.headers["X-Request-ID"]


class SyntheticMailbox:
    """Stateful HTTP fixture, never a real mailbox or provider credential."""

    def __init__(self) -> None:
        self.mail = {"m1": b"Subject: Melron\r\n\r\nSynthetic investment"}
        self.query_state = "q1"
        self.email_state = "e0"
        self.account = "provider-a"
        self.deleted: list[str] = []
        self.updated: list[str] = []
        self.created: list[str] = []
        self.change_state = "e1"
        self.expired = False
        self.status = 200
        self.calls: list[str] = []
        self.keywords: dict[str, bool] = {}
        self.page_size = 1

    def handle(self, request: httpx.Request) -> httpx.Response:
        import json

        self.calls.append(request.method)
        if self.status != 200:
            return httpx.Response(self.status, headers={"Retry-After": "120"})
        if request.method == "GET" and request.url.path.endswith("session"):
            return httpx.Response(
                200,
                json={
                    "primaryAccounts": {MAIL: self.account},
                    "accounts": {self.account: {"accountCapabilities": {MAIL: {}}}},
                    "apiUrl": "https://api.fastmail.com/jmap/api/",
                    "downloadUrl": "https://api.fastmail.com/jmap/download/{blobId}",
                },
            )
        if request.method == "GET":
            return httpx.Response(200, content=self.mail[request.url.path.rsplit("/", 1)[1]])
        method, args, call_id = json.loads(request.content)["methodCalls"][0]
        assert args["accountId"] == self.account
        result: dict[str, Any] = {"accountId": self.account}
        if method == "Email/query":
            position = args["position"]
            ids = sorted(self.mail)[position : position + min(self.page_size, args["limit"])]
            result.update(
                ids=ids, total=len(self.mail), queryState=self.query_state, position=position
            )
        elif method == "Email/get":
            result.update(
                state=self.email_state,
                list=[
                    {
                        "id": key,
                        "blobId": key,
                        "threadId": "thread-1",
                        "receivedAt": "2026-09-19T00:00:00Z",
                        "mailboxIds": {"inbox": True},
                        "keywords": self.keywords,
                    }
                    for key in args["ids"]
                    if key in self.mail
                ],
                notFound=[key for key in args["ids"] if key not in self.mail],
            )
        elif method == "Email/changes":
            if self.expired:
                return httpx.Response(
                    200,
                    json={
                        "methodResponses": [["error", {"type": "cannotCalculateChanges"}, call_id]]
                    },
                )
            result.update(
                oldState=args["sinceState"],
                newState=self.change_state,
                created=self.created,
                updated=self.updated,
                destroyed=self.deleted,
                hasMoreChanges=False,
            )
        else:
            pytest.fail("write/unknown provider method")
        return httpx.Response(200, json={"methodResponses": [[method, result, call_id]]})


def bind_synthetic(database, tenant):
    store, admin = database
    ctx, account = tenant
    with psycopg.connect(admin) as conn:
        conn.execute(
            "UPDATE mail_accounts SET provider_account_id='provider-a' WHERE id=%s", (account,)
        )
    fixture = SyntheticMailbox()
    client = FastmailReadClient(
        "synthetic-transport-token", transport=httpx.MockTransport(fixture.handle)
    )
    return ReadWorker(store, client, jitter=lambda: 0.0), fixture, client


def test_worker_http_to_database_search_and_metadata(database, tenant):
    worker, mail, client = bind_synthetic(database, tenant)
    ctx, account = tenant
    try:
        assert worker.step(ctx, account) == "progress"  # Durable baseline.
        assert worker.step(ctx, account) == "progress"  # Durable listing.
        assert worker.step(ctx, account) == "progress"  # Certified reconciliation.
        mail.keywords = {"$seen": True}
        mail.updated = ["m1"]
        assert worker.step(ctx, account) == "caught_up"
        hits = worker.store.search(ctx, SearchRequest(query="Melron"))
        assert len(hits) == 1
        with worker.store.transaction(ctx) as conn:
            state = conn.execute("SELECT provider_metadata FROM messages").fetchone()
            assert state["provider_metadata"] == {"mailbox_ids": ["inbox"], "keywords": ["$seen"]}
            assert conn.execute("SELECT count(*) AS n FROM sync_runs").fetchone()["n"] == 4
        before = len(mail.calls)
        assert worker.step(ctx, account) == "not_due"
        assert len(mail.calls) == before
    finally:
        client.close()


def test_worker_restart_and_query_churn_preserve_baseline(database, tenant):
    worker, mail, client = bind_synthetic(database, tenant)
    ctx, account = tenant
    mail.mail["m2"] = b"Subject: Survives\r\n\r\nStill present"
    try:
        assert worker.step(ctx, account) == "progress"
        assert worker.step(ctx, account) == "progress"  # First of two listing pages.
        del mail.mail["m1"]
        mail.deleted = ["m1"]
        mail.query_state = "q2"
        mail.email_state = "later-state-do-not-replace-baseline"
        restarted = ReadWorker(worker.store, client)
        assert restarted.step(ctx, account) == "progress"  # Discard stale query position.
        with worker.store.transaction(ctx) as conn:
            cursor = conn.execute("SELECT opaque_cursor FROM sync_cursors").fetchone()[
                "opaque_cursor"
            ]
            checkpoint = Checkpoint.model_validate_json(cursor)
            assert checkpoint.position == 0 and checkpoint.email_state == "e0"
        assert restarted.step(ctx, account) == "progress"
        assert restarted.step(ctx, account) == "progress"  # Remove absent m1 locally.
        assert restarted.step(ctx, account) == "progress"  # Finish reconciliation.
        assert restarted.step(ctx, account) == "caught_up"
        assert worker.store.search(ctx, SearchRequest(query="Melron")) == []
        assert len(worker.store.search(ctx, SearchRequest(query="Survives"))) == 1
    finally:
        client.close()


@pytest.mark.parametrize("status,outcome", [(401, "auth_required"), (429, "retry"), (500, "retry")])
def test_worker_failures_durable_and_no_spin(database, tenant, status, outcome):
    worker, mail, client = bind_synthetic(database, tenant)
    ctx, account = tenant
    mail.status = status
    try:
        assert worker.step(ctx, account) == outcome
        assert worker.step(ctx, account) == "not_due"
        assert len(mail.calls) == 1
        with worker.store.transaction(ctx) as conn:
            assert conn.execute("SELECT count(*) AS n FROM sync_cursors").fetchone()["n"] == 0
            result = conn.execute("SELECT * FROM sync_workers").fetchone()
            assert result["failures"] == 1 and result["last_outcome"] == outcome
    finally:
        client.close()


def test_worker_account_mismatch_fails_before_mail_reads(database, tenant):
    worker, mail, client = bind_synthetic(database, tenant)
    ctx, account = tenant
    mail.account = "other-account"
    try:
        assert worker.step(ctx, account) == "protocol_error"
        assert mail.calls == ["GET"]
    finally:
        client.close()


def test_worker_expired_cursor_rebuilds_before_inference_of_absence(database, tenant):
    worker, mail, client = bind_synthetic(database, tenant)
    ctx, account = tenant
    try:
        worker.step(ctx, account)
        worker.step(ctx, account)
        worker.step(ctx, account)
        mail.expired = True
        del mail.mail["m1"]
        mail.query_state = "q2"
        mail.email_state = "e2"
        assert worker.step(ctx, account) == "progress"
        assert len(worker.store.search(ctx, SearchRequest(query="Melron"))) == 1
        with worker.store.transaction(ctx) as conn:
            cursor = conn.execute("SELECT opaque_cursor FROM sync_cursors").fetchone()[
                "opaque_cursor"
            ]
            assert Checkpoint.model_validate_json(cursor).email_state == "e2"
            assert Checkpoint.model_validate_json(cursor).phase == "listing"
        assert worker.step(ctx, account) == "progress"  # Seal empty inventory.
        assert len(worker.store.search(ctx, SearchRequest(query="Melron"))) == 1
        assert worker.step(ctx, account) == "progress"  # Now infer absence.
        assert worker.store.search(ctx, SearchRequest(query="Melron")) == []
        assert worker.step(ctx, account) == "progress"
        mail.expired = False
        assert worker.step(ctx, account) == "caught_up"
        with worker.store.transaction(ctx) as conn:
            assert conn.execute("SELECT count(*) AS n FROM raw_objects").fetchone()["n"] == 1
    finally:
        client.close()


def test_worker_bad_mime_is_preserved_and_does_not_block_good_mail(database, tenant):
    worker, mail, client = bind_synthetic(database, tenant)
    ctx, account = tenant
    try:
        worker.step(ctx, account)
        mail.mail["m1"] = b""
        mail.mail["m2"] = b"Subject: Survives\r\n\r\nHealthy content"
        assert worker.step(ctx, account) == "progress"
        with worker.store.transaction(ctx) as conn:
            cursor = conn.execute("SELECT opaque_cursor FROM sync_cursors").fetchone()[
                "opaque_cursor"
            ]
            assert Checkpoint.model_validate_json(cursor).phase == "listing"
            assert conn.execute("SELECT count(*) AS n FROM messages").fetchone()["n"] == 0
            assert conn.execute("SELECT raw_mime FROM raw_objects").fetchone()["raw_mime"] == b""
            assert (
                conn.execute("SELECT reason FROM quarantine_receipts").fetchone()["reason"]
                == "mime_rejected"
            )
        assert worker.step(ctx, account) == "progress"
        assert worker.step(ctx, account) == "progress"
        assert worker.step(ctx, account) == "caught_up"
        assert len(worker.store.search(ctx, SearchRequest(query="Survives"))) == 1
    finally:
        client.close()


def test_worker_leases_competing_and_expired_process_fenced(database, tenant):
    worker, _, client = bind_synthetic(database, tenant)
    ctx, account = tenant
    _, admin = database
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(
                pool.map(lambda _: SyncStore(worker.store).acquire(ctx, account), range(8))
            )
        acquired = [lease for lease in results if lease]
        assert len(acquired) == 1
        old = acquired[0]
        with psycopg.connect(admin) as conn:
            conn.execute(
                "UPDATE sync_workers SET lease_until=now()-interval '1 second' WHERE account_id=%s",
                (account,),
            )
        new = worker.jobs.acquire(ctx, account)
        assert new is not None and new.token != old.token
        with pytest.raises(Conflict):
            worker.jobs.renew(ctx, account, old.token)
        with pytest.raises(Conflict):
            worker.store.ingest_page(ctx, account, None, "bad", [item()], lease_token=old.token)
        with pytest.raises(Conflict):
            worker.store.ingest_page(ctx, account, None, "bad", [item()])
        assert (
            worker.store.ingest_page(ctx, account, None, "ok", [item()], lease_token=new.token) == 1
        )
        with pytest.raises(Conflict):
            worker.jobs.finish(ctx, account, old.token, "caught_up")
        worker.jobs.finish(ctx, account, new.token, "progress", 1)
    finally:
        client.close()


def test_worker_db_commit_crash_replay_is_harmless(database, tenant):
    worker, _, client = bind_synthetic(database, tenant)
    ctx, account = tenant
    _, admin = database
    try:
        lease = worker.jobs.acquire(ctx, account)
        assert lease
        assert (
            worker.store.ingest_page(
                ctx, account, None, "committed", [item()], lease_token=lease.token
            )
            == 1
        )
        # Crash after commit and before finish; expire the abandoned lease.
        with psycopg.connect(admin) as conn:
            conn.execute(
                "UPDATE sync_workers SET lease_until=now()-interval '1 second' WHERE account_id=%s",
                (account,),
            )
        fresh = worker.jobs.acquire(ctx, account)
        assert fresh and fresh.cursor == "committed"
        assert (
            worker.store.ingest_page(
                ctx, account, None, "committed", [item()], lease_token=fresh.token
            )
            == 0
        )
        with worker.store.transaction(ctx) as conn:
            assert conn.execute("SELECT count(*) AS n FROM messages").fetchone()["n"] == 1
    finally:
        client.close()


def test_worker_requires_enrollment_and_scope(database, tenant):
    store, _ = database
    ctx, account = tenant
    with pytest.raises(NotFound):
        SyncStore(store).acquire(ctx, account)
    with pytest.raises(AccessDenied):
        SyncStore(store).acquire(replace(ctx, scopes=frozenset()), account)


def test_worker_enrollment_change_fences_old_binding(database, tenant):
    worker, _, client = bind_synthetic(database, tenant)
    ctx, account = tenant
    _, admin = database
    try:
        lease = worker.jobs.acquire(ctx, account)
        assert lease
        with psycopg.connect(admin) as conn:
            conn.execute(
                "UPDATE mail_accounts SET provider_account_id='replacement' WHERE id=%s", (account,)
            )
        with pytest.raises(Conflict):
            worker.store.ingest_page(ctx, account, None, "no", [item()], lease_token=lease.token)
        with worker.store.transaction(ctx) as conn:
            assert conn.execute("SELECT count(*) AS n FROM messages").fetchone()["n"] == 0
    finally:
        client.close()


def test_worker_tables_rls_and_append_only_runs(database, tenant):
    worker, _, client = bind_synthetic(database, tenant)
    ctx, account = tenant
    _, admin = database
    try:
        worker.step(ctx, account)
        with psycopg.connect(worker.store.dsn) as conn:
            assert conn.execute("SELECT count(*) FROM sync_workers").fetchone() == (0,)
            assert conn.execute("SELECT count(*) FROM sync_runs").fetchone() == (0,)
            conn.execute("SELECT set_config('email_brain.tenant_id',%s,true)", (str(uuid4()),))
            assert conn.execute("SELECT count(*) FROM sync_workers").fetchone() == (0,)
        with pytest.raises(psycopg.errors.RaiseException), psycopg.connect(admin) as conn:
            conn.execute(
                "UPDATE sync_runs SET outcome='retry' WHERE tenant_id=%s", (ctx.tenant_id,)
            )
    finally:
        client.close()


def test_uncertified_or_incomplete_inventory_never_authorizes_absence(database, tenant):
    store, _ = database
    ctx, account = tenant
    generation = uuid4()
    store.ingest_page(ctx, account, None, "existing", [item()])
    with pytest.raises(InventoryError):
        SyncStore(store).reconciliation_candidates(ctx, account, generation)
    with pytest.raises(InventoryError):
        store.ingest_page(
            ctx,
            account,
            "existing",
            "wrong",
            [],
            inventory_generation=generation,
            inventory_total=1,
        )
    assert len(store.search(ctx, SearchRequest(query="Melron"))) == 1
    with store.transaction(ctx) as conn:
        assert conn.execute("SELECT count(*) AS n FROM sync_inventory_seals").fetchone()["n"] == 0
        assert (
            conn.execute("SELECT opaque_cursor FROM sync_cursors").fetchone()["opaque_cursor"]
            == "existing"
        )


def test_quarantine_update_replay_recovery_and_evidence(database, tenant):
    store, _ = database
    ctx, account = tenant
    store.ingest_page(ctx, account, None, "c1", [item()])
    evidence = store.search(ctx, SearchRequest(query="Melron"))[0]["evidence_id"]
    bad = replace(item("poison"), raw=b"")
    assert store.ingest_page(ctx, account, "c1", "c2", [bad]) == 1
    assert store.ingest_page(ctx, account, "c1", "c2", [bad]) == 0
    assert store.search(ctx, SearchRequest(query="Melron")) == []
    assert store.evidence(ctx, evidence)
    assert store.sync_status(ctx, account)["review_required"]
    store.ingest_page(ctx, account, "c2", "c3", [item("fixed")])
    assert len(store.search(ctx, SearchRequest(query="Melron"))) == 1
    assert not store.sync_status(ctx, account)["review_required"]
    with store.transaction(ctx) as conn:
        assert conn.execute("SELECT count(*) AS n FROM quarantine_receipts").fetchone()["n"] == 1
        assert conn.execute("SELECT count(*) AS n FROM raw_objects").fetchone()["n"] == 2


def test_duplicate_across_inventory_pages_cannot_certify_a_missing_id(database, tenant):
    store, _ = database
    ctx, account = tenant
    generation = uuid4()
    store.ingest_page(ctx, account, None, "page1", [item()], inventory_generation=generation)
    # Provider repeats page one's ID while claiming that two distinct IDs exist.
    with pytest.raises(InventoryError):
        store.ingest_page(
            ctx,
            account,
            "page1",
            "done",
            [item("repeat")],
            inventory_generation=generation,
            inventory_total=2,
        )
    with store.transaction(ctx) as conn:
        assert conn.execute("SELECT count(*) AS n FROM sync_inventory").fetchone()["n"] == 1
        assert conn.execute("SELECT count(*) AS n FROM provider_events").fetchone()["n"] == 1
        assert conn.execute("SELECT count(*) AS n FROM sync_inventory_seals").fetchone()["n"] == 0
    with pytest.raises(InventoryError):
        SyncStore(store).reconciliation_candidates(ctx, account, generation)


def test_deleted_quarantine_has_no_unresolved_status_but_preserves_receipt(database, tenant):
    store, _ = database
    ctx, account = tenant
    store.ingest_page(ctx, account, None, "q", [replace(item(), raw=b"")])
    store.ingest_page(ctx, account, "q", "d", [replace(item("deleted"), raw=None)])
    status = store.sync_status(ctx, account)
    assert status["message_counts"] == {"ready": 0, "quarantined": 0, "deleted": 1}
    assert not status["review_required"]
    with store.transaction(ctx) as conn:
        assert conn.execute("SELECT count(*) AS n FROM quarantine_receipts").fetchone()["n"] == 1
        assert conn.execute("SELECT raw_mime FROM raw_objects").fetchone()["raw_mime"] == b""


def test_quarantine_inventory_rls_and_immutability(database, tenant):
    store, admin = database
    ctx, account = tenant
    generation = uuid4()
    store.ingest_page(
        ctx,
        account,
        None,
        "c",
        [replace(item(), raw=b"")],
        inventory_generation=generation,
        inventory_total=1,
    )
    for table in (
        "sync_inventory",
        "sync_inventory_seals",
        "quarantine_receipts",
        "message_sync_state",
    ):
        with psycopg.connect(store.dsn) as conn:
            assert conn.execute(
                sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))
            ).fetchone() == (0,)
            conn.execute("SELECT set_config('email_brain.tenant_id',%s,true)", (str(uuid4()),))
            assert conn.execute(
                sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))
            ).fetchone() == (0,)
    for table in ("sync_inventory", "sync_inventory_seals", "quarantine_receipts"):
        with pytest.raises(psycopg.errors.RaiseException), psycopg.connect(admin) as conn:
            conn.execute(
                sql.SQL("DELETE FROM {} WHERE tenant_id=%s").format(sql.Identifier(table)),
                (ctx.tenant_id,),
            )
    with pytest.raises(NotFound):
        store.sync_status(ctx, uuid4())
    with pytest.raises(AccessDenied):
        store.sync_status(replace(ctx, scopes=frozenset()), account)


def test_legacy_checkpoint_restarts_full_inventory_without_hiding_mail(database, tenant):
    store, _ = database
    ctx, account = tenant
    old = Checkpoint(schema_version=1, generation=uuid4(), phase="changes", email_state="old")
    store.ingest_page(ctx, account, None, old.encode(), [item()])
    worker, _, client = bind_synthetic(database, tenant)
    try:
        assert worker.step(ctx, account) == "progress"
        with store.transaction(ctx) as conn:
            checkpoint = Checkpoint.model_validate_json(
                conn.execute("SELECT opaque_cursor FROM sync_cursors").fetchone()["opaque_cursor"]
            )
            assert checkpoint.schema_version == 2 and checkpoint.phase == "listing"
            assert checkpoint.generation != old.generation
        assert len(store.search(ctx, SearchRequest(query="Melron"))) == 1
    finally:
        client.close()


def test_synthetic_256_mailbox_import_search_attachments_and_restart(database, tenant):
    worker, mail, client = bind_synthetic(database, tenant)
    ctx, account = tenant
    mail.mail = {f"m{i:05d}": fake_email(i) for i in range(256)}
    mail.page_size = 8
    try:
        outcomes = []
        for _ in range(40):
            # New process object at every page, using only durable database state.
            result = ReadWorker(worker.store, client, jitter=lambda: 0.0).step(ctx, account)
            outcomes.append(result)
            if result == "caught_up":
                break
            assert result == "progress"
        assert outcomes[-1] == "caught_up" and len(outcomes) == 35
        state = worker.store.sync_status(ctx, account)
        assert state["message_counts"] == {"ready": 256, "quarantined": 0, "deleted": 0}
        for index in (0, 4, 5, 7, 127, 255):
            hits = worker.store.search(ctx, SearchRequest(query=f"marker{index:05d}"))
            assert len(hits) == 1
            assert worker.store.evidence(ctx, hits[0]["evidence_id"])
        with worker.store.transaction(ctx) as conn:
            assert (
                conn.execute("SELECT count(*) AS n FROM attachment_receipts").fetchone()["n"] == 64
            )
            assert (
                conn.execute(
                    "SELECT count(*) AS n FROM attachment_receipts WHERE duplicate_of IS NOT NULL"
                ).fetchone()["n"]
                == 62
            )
            assert conn.execute("SELECT total FROM sync_inventory_seals").fetchone()["total"] == 256
        assert worker.step(ctx, account) == "not_due"
        # Simulate the scheduler's next tick, then a seven-ID incremental delta.
        with psycopg.connect(database[1]) as conn:
            conn.execute(
                "UPDATE sync_workers SET next_attempt_at=now() WHERE account_id=%s", (account,)
            )
        mail.updated = ["m00000", "m00004", "m00005"]
        mail.created = ["m00256", "m00257"]
        mail.deleted = ["m00002", "m00003"]
        mail.change_state = mail.email_state = "e2"
        for key in mail.deleted:
            del mail.mail[key]
        for index in (0, 4, 256, 257):
            mail.mail[f"m{index:05d}"] = fake_email(index + 1000)
        mail.mail["m00005"] = b""
        assert worker.step(ctx, account) == "caught_up"
        assert worker.store.sync_status(ctx, account)["message_counts"] == {
            "ready": 255,
            "quarantined": 1,
            "deleted": 2,
        }
        assert worker.store.search(ctx, SearchRequest(query="marker00000")) == []
        assert len(worker.store.search(ctx, SearchRequest(query="marker01000"))) == 1
        # Expired history plus twenty unseen deletions: the certified full rebuild
        # must recover them in bounded reconciliation pages, not leave stale hits.
        with psycopg.connect(database[1]) as conn:
            conn.execute(
                "UPDATE sync_workers SET next_attempt_at=now() WHERE account_id=%s", (account,)
            )
        for index in range(10, 30):
            del mail.mail[f"m{index:05d}"]
        mail.expired = True
        mail.email_state = mail.change_state = "e4"
        mail.query_state = "q4"
        mail.updated, mail.created, mail.deleted = [], [], []
        assert worker.step(ctx, account) == "progress"
        assert len(worker.store.search(ctx, SearchRequest(query="marker00010"))) == 1
        mail.expired = False
        for _ in range(40):
            result = worker.step(ctx, account)
            if result == "caught_up":
                break
            assert result == "progress"
        assert result == "caught_up"
        assert worker.store.sync_status(ctx, account)["message_counts"] == {
            "ready": 235,
            "quarantined": 1,
            "deleted": 22,
        }
        assert worker.store.search(ctx, SearchRequest(query="marker00010")) == []
    finally:
        client.close()


def test_seed_corpus_cli_resumes_after_mid_import_crash(database, tenant, tmp_path, monkeypatch):
    import json

    from email_brain.cli import seed_corpus

    store, _ = database
    ctx, account = tenant
    (tmp_path / "demo.json").write_text(
        json.dumps(
            {
                "tenant_id": str(ctx.tenant_id),
                "actor_id": str(ctx.actor_id),
                "account_id": str(account),
            }
        )
    )
    monkeypatch.setenv("EMAIL_BRAIN_DSN", store.dsn)
    real_ingest = Store.ingest_page
    calls = 0

    def interrupted(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("synthetic crash")
        return real_ingest(self, *args, **kwargs)

    monkeypatch.setattr(Store, "ingest_page", interrupted)
    with pytest.raises(RuntimeError, match="synthetic crash"):
        seed_corpus(tmp_path, 205)
    assert store.sync_status(ctx, account)["message_counts"]["ready"] == 100
    monkeypatch.setattr(Store, "ingest_page", real_ingest)
    seed_corpus(tmp_path, 205)
    seed_corpus(tmp_path, 205)  # Complete replay is harmless.
    assert store.sync_status(ctx, account)["message_counts"]["ready"] == 205
    with store.transaction(ctx) as conn:
        assert conn.execute("SELECT count(*) AS n FROM provider_events").fetchone()["n"] == 205
    with pytest.raises(ValueError, match="matching corpus"):
        seed_corpus(tmp_path, 206)
    with psycopg.connect(database[1]) as conn:
        conn.execute(
            "UPDATE mail_accounts SET provider_account_id='real-binding' WHERE id=%s", (account,)
        )
    with pytest.raises(ValueError, match="unenrolled synthetic"):
        seed_corpus(tmp_path, 205)


def test_sync_status_api_uses_database_owner_and_hides_unknown_accounts(database, tenant):
    store, _ = database
    ctx, account = tenant
    token = "synthetic-status-test-not-a-real-credential-00000"
    credential = Credential(
        token_sha256=hashlib.sha256(token.encode()).hexdigest(),
        tenant_id=ctx.tenant_id,
        actor_id=ctx.actor_id,
        scopes={"email.search"},
        client_kind="human",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    client = TestClient(create_app(store, TokenRegistry([credential])))
    headers = {"Authorization": f"Bearer {token}"}
    store.ingest_page(ctx, account, None, "c", [replace(item(), raw=b"")])
    result = client.get(f"/v1/accounts/{account}/sync-status", headers=headers)
    assert result.status_code == 200 and result.json()["review_required"]
    assert result.json()["message_counts"]["quarantined"] == 1
    assert "raw" not in result.text and "secret" not in result.text
    assert client.get(f"/v1/accounts/{uuid4()}/sync-status", headers=headers).status_code == 404
    with psycopg.connect(database[1]) as conn:
        conn.execute("DELETE FROM tenant_memberships WHERE tenant_id=%s", (ctx.tenant_id,))
    assert client.get(f"/v1/accounts/{account}/sync-status", headers=headers).status_code == 403


def test_fileos_incomplete_snapshot_cannot_advance_absence(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID], tmp_path: Path
) -> None:
    store, _ = database
    ctx, _ = tenant
    ctx = datacore_context(ctx)
    source_id = "files_coverage_guard"
    (tmp_path / "kept.txt").write_bytes(b"fictional kept evidence")
    missing = tmp_path / "missing.txt"
    missing.write_bytes(b"fictional missing evidence")
    core = DataCoreStore(store)

    def record(manifest: dict[str, Any], run_id: UUID) -> None:
        core.import_fileos_snapshot(ctx, manifest, run_id)
        core.complete_fileos_run(
            ctx,
            manifest,
            run_id,
            outcomes={"unsupported": len(manifest["items"])},
            item_outcomes={item["item_id"]: "unsupported" for item in manifest["items"]},
            published_documents=0,
            code_revision="test-coverage-v1",
            document_processor_version=None,
        )

    first = fileos_manifest(tmp_path, source_id=source_id, hour=1)
    first_run = uuid4()
    record(first, first_run)
    assert core.fileos_inventory(ctx, source_id)["newly_absent_items"] == 0

    partial = fileos_manifest(tmp_path, source_id=source_id, hour=2)
    partial["items"] = [item for item in partial["items"] if item["locator"] == "kept.txt"]
    partial["counts"]["items"] = 1
    partial["counts"]["errors"] = 1
    partial["errors"] = [{"locator": "missing.txt", "code": "file_unreadable"}]
    partial_run = uuid4()
    core.import_fileos_snapshot(ctx, partial, partial_run)
    with pytest.raises(ValueError, match="coverage"):
        core.complete_fileos_run(
            ctx,
            partial,
            partial_run,
            outcomes={"unsupported": 1},
            item_outcomes={partial["items"][0]["item_id"]: "unsupported"},
            published_documents=0,
            code_revision="test-coverage-v1",
            document_processor_version=None,
        )
    inventory = core.fileos_inventory(ctx, source_id)
    assert inventory["run_id"] == first_run
    assert inventory["newly_absent_items"] == 0
    with store.transaction(ctx) as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM brain_fileos_absence_events WHERE source_id=%s",
                (source_id,),
            ).fetchone()["n"]
            == 0
        )

    missing.unlink()
    clean = fileos_manifest(tmp_path, source_id=source_id, hour=3)
    clean_run = uuid4()
    record(clean, clean_run)
    inventory = core.fileos_inventory(ctx, source_id)
    assert inventory["run_id"] == clean_run
    assert inventory["newly_absent_items"] == 1


def test_fileos_source_refuses_different_physical_root_before_intake(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID], tmp_path: Path
) -> None:
    store, _ = database
    ctx, _ = tenant
    ctx = datacore_context(ctx)
    core = DataCoreStore(store)
    source_id = "files_root_bound"
    original = tmp_path / "original"
    other = tmp_path / "other"
    original.mkdir()
    other.mkdir()
    (original / "proof.txt").write_bytes(b"fictional proof")
    (other / "proof.txt").write_bytes(b"fictional proof")
    first = fileos_manifest(original, source_id=source_id)
    first_run = uuid4()
    core.import_fileos_snapshot(ctx, first, first_run)
    core.complete_fileos_run(
        ctx,
        first,
        first_run,
        outcomes={"unsupported": 1},
        item_outcomes={first["items"][0]["item_id"]: "unsupported"},
        published_documents=0,
        code_revision="test-root-binding-v1",
        document_processor_version=None,
    )
    different = fileos_manifest(other, source_id=source_id, hour=2)
    with pytest.raises(Conflict, match="source root binding changed"):
        core.import_fileos_snapshot(ctx, different, uuid4())
    assert core.fileos_inventory(ctx, source_id)["run_id"] == first_run
    with store.transaction(ctx) as conn:
        assert (
            conn.execute(
                "SELECT root_binding_sha256 FROM brain_sources WHERE id=%s", (source_id,)
            ).fetchone()["root_binding_sha256"]
            == first["root_binding"]["sha256"]
        )
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM brain_fileos_run_receipts WHERE source_id=%s",
                (source_id,),
            ).fetchone()["n"]
            == 1
        )
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM brain_fileos_absence_events WHERE source_id=%s",
                (source_id,),
            ).fetchone()["n"]
            == 0
        )


def test_fileos_mass_loss_refuses_completion_without_absence(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID], tmp_path: Path
) -> None:
    store, _ = database
    ctx, _ = tenant
    ctx = datacore_context(ctx)
    source_id = "files_mass_loss_guard"
    core = DataCoreStore(store)
    for number in range(20):
        (tmp_path / f"fictional_{number:02}.bin").write_bytes(f"fictional {number}".encode())

    def record(manifest: dict[str, Any], run_id: UUID) -> bool:
        core.import_fileos_snapshot(ctx, manifest, run_id)
        return core.complete_fileos_run(
            ctx,
            manifest,
            run_id,
            outcomes={"unsupported": len(manifest["items"])},
            item_outcomes={item["item_id"]: "unsupported" for item in manifest["items"]},
            published_documents=0,
            code_revision="test-mass-loss-v1",
            document_processor_version=None,
        ).recorded

    first = fileos_manifest(tmp_path, source_id=source_id, hour=1)
    first_run = uuid4()
    assert record(first, first_run) is True
    assert record(first, first_run) is False
    with store.transaction(ctx) as conn:
        saved = conn.execute(
            "SELECT policy_sha256 FROM brain_fileos_run_receipts WHERE actor_id=%s AND run_id=%s",
            (ctx.actor_id, first_run),
        ).fetchone()
        assert saved["policy_sha256"] == fileos_inventory_policy_sha256(first)

    held = tmp_path.parent / f"{tmp_path.name}_held"
    held.mkdir()
    for number in range(10):
        (tmp_path / f"fictional_{number:02}.bin").rename(held / f"fictional_{number:02}.bin")
    thin = fileos_manifest(tmp_path, source_id=source_id, hour=2)
    thin_run = uuid4()
    with pytest.raises(Conflict, match="mass loss requires review"):
        record(thin, thin_run)
    assert core.fileos_inventory(ctx, source_id)["run_id"] == first_run
    with store.transaction(ctx) as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM brain_fileos_run_receipts WHERE source_id=%s",
                (source_id,),
            ).fetchone()["n"]
            == 1
        )
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM brain_fileos_absence_events WHERE source_id=%s",
                (source_id,),
            ).fetchone()["n"]
            == 0
        )

    for number in range(2):
        (held / f"fictional_{number:02}.bin").rename(tmp_path / f"fictional_{number:02}.bin")
    clean = fileos_manifest(tmp_path, source_id=source_id, hour=3)
    clean_run = uuid4()
    assert record(clean, clean_run) is True
    inventory = core.fileos_inventory(ctx, source_id)
    assert inventory["run_id"] == clean_run
    assert inventory["newly_absent_items"] == 8


def test_fileos_policy_drift_cannot_infer_absence(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID], tmp_path: Path
) -> None:
    store, admin = database
    ctx, _ = tenant
    ctx = datacore_context(ctx)
    source_id = "files_policy_guard"
    core = DataCoreStore(store)
    (tmp_path / "kept.txt").write_bytes(b"fictional kept evidence")
    gone = tmp_path / "gone.txt"
    gone.write_bytes(b"fictional removed evidence")

    def record(manifest: dict[str, Any], run_id: UUID) -> bool:
        core.import_fileos_snapshot(ctx, manifest, run_id)
        return core.complete_fileos_run(
            ctx,
            manifest,
            run_id,
            outcomes={"unsupported": len(manifest["items"])},
            item_outcomes={item["item_id"]: "unsupported" for item in manifest["items"]},
            published_documents=0,
            code_revision="test-policy-v1",
            document_processor_version=None,
        ).recorded

    first = fileos_manifest(tmp_path, source_id=source_id, hour=1)
    first_run = uuid4()
    assert record(first, first_run) is True
    assert record(first, first_run) is False

    changes = [
        {"config": {"exclude_patterns": ["gone.txt"]}},
        {"config": {"max_file_size_mb": 1}},
        {"follow_file_symlinks": True},
    ]
    for hour, options in enumerate(changes, start=2):
        changed = snapshot_tree(
            tmp_path,
            source_id=source_id,
            observed_at=datetime(2026, 9, 22, hour, tzinfo=UTC),
            **options,
        )
        with pytest.raises(Conflict, match="inventory policy requires review"):
            record(changed, uuid4())
        assert core.fileos_inventory(ctx, source_id)["run_id"] == first_run
    with store.transaction(ctx) as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM brain_fileos_run_receipts WHERE source_id=%s",
                (source_id,),
            ).fetchone()["n"]
            == 1
        )
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM brain_fileos_absence_events WHERE source_id=%s",
                (source_id,),
            ).fetchone()["n"]
            == 0
        )

    gone.unlink()
    clean = fileos_manifest(tmp_path, source_id=source_id, hour=5)
    clean_run = uuid4()
    assert record(clean, clean_run) is True
    assert core.fileos_inventory(ctx, source_id)["newly_absent_items"] == 1
    with pytest.raises(psycopg.errors.CheckViolation), psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO brain_fileos_run_receipts(tenant_id,actor_id,run_id,source_id,"
            "observed_at,manifest_sha256,code_revision,text_extractor_version,item_count,"
            "outcomes,published_documents) VALUES (%s,%s,%s,%s,now(),%s,"
            "'test-policy-v1','fileos-text-v1',0,'{}'::jsonb,0)",
            (ctx.tenant_id, ctx.actor_id, uuid4(), source_id, "a" * 64),
        )


@pytest.mark.parametrize("transition", ["oversize", "symlink_file", "symlink_directory"])
def test_fileos_excluded_prior_locator_cannot_become_absence(
    database: tuple[Store, str],
    tenant: tuple[TenantContext, UUID],
    tmp_path: Path,
    transition: str,
) -> None:
    store, _ = database
    ctx, _ = tenant
    ctx = datacore_context(ctx)
    source_id = "files_exclusion_" + transition
    core = DataCoreStore(store)
    (tmp_path / "kept.txt").write_bytes(b"fictional kept evidence")
    target = (
        tmp_path / "sub" / "target.txt"
        if transition == "symlink_directory"
        else tmp_path / "target.txt"
    )
    target.parent.mkdir(exist_ok=True)
    target.write_bytes(b"fictional target evidence")
    policy = {
        "min_file_size": 0,
        "max_file_size_mb": 1,
        "include_extensions": None,
        "exclude_patterns": [],
    }

    def snapshot(hour: int) -> dict[str, Any]:
        return snapshot_tree(
            tmp_path,
            source_id=source_id,
            observed_at=datetime(2026, 9, 22, hour, tzinfo=UTC),
            config=policy,
        )

    def complete(manifest: dict[str, Any], run_id: UUID) -> bool:
        core.import_fileos_snapshot(ctx, manifest, run_id)
        count = len(manifest["items"])
        return core.complete_fileos_run(
            ctx,
            manifest,
            run_id,
            outcomes={"unsupported": count} if count else {},
            item_outcomes={item["item_id"]: "unsupported" for item in manifest["items"]},
            published_documents=0,
            code_revision="test-exclusion-v1",
            document_processor_version=None,
        ).recorded

    first = snapshot(1)
    first_run = uuid4()
    assert complete(first, first_run)
    if transition == "oversize":
        target.write_bytes(b"x" * (1_048_576 + 1))
    elif transition == "symlink_file":
        target.unlink()
        target.symlink_to(tmp_path / "kept.txt")
    else:
        prior_dir = target.parent
        prior_dir.rename(tmp_path / "outside")
        prior_dir.symlink_to(tmp_path / "outside", target_is_directory=True)
    excluded = snapshot(2)
    with pytest.raises(Conflict, match="excluded prior item requires review"):
        complete(excluded, uuid4())
    assert core.fileos_inventory(ctx, source_id)["run_id"] == first_run
    with store.transaction(ctx) as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM brain_fileos_run_receipts WHERE source_id=%s",
                (source_id,),
            ).fetchone()["n"]
            == 1
        )
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM brain_fileos_absence_events WHERE source_id=%s",
                (source_id,),
            ).fetchone()["n"]
            == 0
        )

    if transition == "symlink_directory":
        (tmp_path / "sub").unlink()
    else:
        target.unlink()
    genuinely_absent = snapshot(3)
    final_run = uuid4()
    assert complete(genuinely_absent, final_run)
    inventory = core.fileos_inventory(ctx, source_id)
    assert inventory["run_id"] == final_run
    assert inventory["newly_absent_items"] == 1


def test_fileos_donor_preview_requires_latest_exact_completed_v1_run(
    database: tuple[Store, str],
    tenant: tuple[TenantContext, UUID],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _ = database
    ctx = datacore_context(tenant[0])
    core = DataCoreStore(store)
    source_id = "files_donor_baseline"
    (tmp_path / "proof.txt").write_bytes(b"fictional completed baseline proof")
    prior = fileos_manifest(tmp_path, source_id=source_id, hour=1)
    first_run = uuid4()

    with pytest.raises(Conflict, match="completed baseline"):
        core.verify_fileos_completed_baseline(ctx, prior, first_run)
    core.import_fileos_snapshot(ctx, prior, first_run)
    with pytest.raises(Conflict, match="completed baseline"):
        core.verify_fileos_completed_baseline(ctx, prior, first_run)

    def complete(manifest: dict[str, Any], run_id: UUID) -> None:
        core.import_fileos_snapshot(ctx, manifest, run_id)
        core.complete_fileos_run(
            ctx, manifest, run_id,
            outcomes={"unsupported": len(manifest["items"])},
            item_outcomes={item["item_id"]: "unsupported" for item in manifest["items"]},
            published_documents=0,
            code_revision="test-donor-baseline-v1",
            document_processor_version=None,
        )

    core.complete_fileos_run(
        ctx, prior, first_run,
        outcomes={"unsupported": 1},
        item_outcomes={prior["items"][0]["item_id"]: "unsupported"},
        published_documents=0,
        code_revision="test-donor-baseline-v1",
        document_processor_version=None,
    )
    completed_at = core.verify_fileos_completed_baseline(ctx, prior, first_run)
    assert completed_at.tzinfo is not None
    with pytest.raises(AccessDenied):
        core.verify_fileos_completed_baseline(replace(ctx, scopes=frozenset()), prior, first_run)
    report = preview_fileos_completed_donor_transition(
        core, ctx, prior, first_run, tmp_path,
        source_id=source_id,
        observed_at=datetime(2026, 9, 22, 3, tzinfo=UTC),
    )
    assert report["publishable"] is False
    assert report["counts"]["unchanged"] == 1
    assert report["completed_baseline"]["run_id"] == str(first_run)
    with pytest.raises(Conflict, match="completed baseline"):
        core.verify_fileos_completed_baseline(ctx, prior, uuid4())
    changed_policy = json.loads(json.dumps(prior))
    changed_policy["policy"]["min_file_size"] = 1
    with pytest.raises(Conflict, match="completed baseline"):
        core.verify_fileos_completed_baseline(ctx, changed_policy, first_run)

    second = fileos_manifest(tmp_path, source_id=source_id, hour=2)
    original_candidate = transition_module.build_fileos_donor_candidate

    def complete_during_scan(root: Path, **kwargs: Any) -> dict[str, Any]:
        complete(second, uuid4())
        return original_candidate(root, **kwargs)

    monkeypatch.setattr(transition_module, "build_fileos_donor_candidate", complete_during_scan)
    with pytest.raises(Conflict, match="completed baseline"):
        preview_fileos_completed_donor_transition(
            core, ctx, prior, first_run, tmp_path,
            source_id=source_id,
            observed_at=datetime(2026, 9, 22, 3, tzinfo=UTC),
        )
    with pytest.raises(Conflict, match="completed baseline"):
        core.verify_fileos_completed_baseline(ctx, prior, first_run)
    monkeypatch.setattr(
        "masterbrain.datacore.fileos_donor_transition.build_fileos_donor_candidate",
        lambda *_args, **_kwargs: pytest.fail("stale baseline started donor scan"),
    )
    with pytest.raises(Conflict, match="completed baseline"):
        preview_fileos_completed_donor_transition(
            core, ctx, prior, first_run, tmp_path,
            source_id=source_id,
            observed_at=datetime(2026, 9, 22, 3, tzinfo=UTC),
        )


def test_fileos_transition_review_packet_is_immutable_nonpublishing_and_run_bound(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID], tmp_path: Path
) -> None:
    store, admin = database
    ctx = datacore_context(tenant[0])
    core = DataCoreStore(store)
    source_id = "files_transition_packet"
    proof = tmp_path / "proof.txt"
    proof.write_bytes(b"fictional immutable packet proof")
    prior = fileos_manifest(tmp_path, source_id=source_id, hour=1)
    first_run = uuid4()
    core.import_fileos_snapshot(ctx, prior, first_run)
    core.complete_fileos_run(
        ctx, prior, first_run,
        outcomes={"unsupported": 1},
        item_outcomes={prior["items"][0]["item_id"]: "unsupported"},
        published_documents=0,
        code_revision="test-packet-v1",
        document_processor_version=None,
    )
    observed = datetime(2026, 9, 22, 3, tzinfo=UTC)
    packet_id = uuid4()
    first = record_fileos_transition_review(
        core, ctx, prior, first_run, packet_id, tmp_path,
        source_id=source_id, observed_at=observed,
    )
    assert first.recorded is True
    assert len(first.packet_sha256) == 64
    replay = record_fileos_transition_review(
        core, ctx, prior, first_run, packet_id, tmp_path,
        source_id=source_id, observed_at=observed,
    )
    assert replay == replace(first, recorded=False)
    summary = core.fileos_transition_review(ctx, packet_id)
    assert summary["latest_receipt_matches_packet"] is True
    assert summary["packet_sha256"] == first.packet_sha256
    assert summary["detail_total"] == 2
    assert summary["classification_counts"]["unchanged"] == 1
    assert "proof.txt" not in json.dumps(summary, default=str)
    assert "details" not in summary
    with pytest.raises(AccessDenied):
        core.fileos_transition_review(ctx, packet_id, include_details=True)
    detail_ctx = replace(ctx, scopes=ctx.scopes | frozenset({"brain.evidence.read"}))
    first_page = core.fileos_transition_review(
        detail_ctx, packet_id, include_details=True, limit=1
    )
    assert first_page["details"][0]["ledger"] == "prior"
    assert first_page["details"][0]["locator"] == "proof.txt"
    assert first_page["next_offset"] == 1
    second_page = core.fileos_transition_review(
        detail_ctx, packet_id, include_details=True, offset=1, limit=1
    )
    assert second_page["details"][0]["ledger"] == "hashed"
    assert second_page["details"][0]["sha256"] == prior["items"][0]["digest"]["value"]
    assert second_page["next_offset"] is None
    with psycopg.connect(admin) as conn:
        audit = conn.execute(
            "SELECT resource_type,resource_id,metadata FROM audit_events "
            "WHERE tenant_id=%s AND event_type='brain.fileos_transition_review_read' "
            "ORDER BY occurred_at DESC,id DESC LIMIT 1",
            (ctx.tenant_id,),
        ).fetchone()
        assert audit == ("fileos_transition_packet", str(packet_id), {})
    with pytest.raises(ValueError, match="review request"):
        core.fileos_transition_review(ctx, packet_id, offset=1)
    other_tenant, other_actor = uuid4(), uuid4()
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO tenants(id,name) VALUES (%s,'Other fictional tenant')",
            (other_tenant,),
        )
        conn.execute(
            "INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES (%s,%s,'owner')",
            (other_tenant, other_actor),
        )
    with pytest.raises(NotFound):
        core.fileos_transition_review(
            replace(ctx, tenant_id=other_tenant, actor_id=other_actor), packet_id
        )
    with store.transaction(ctx) as conn:
        row = conn.execute(
            "SELECT packet,packet_sha256 FROM brain_fileos_transition_packets WHERE id=%s",
            (packet_id,),
        ).fetchone()
        assert row is not None and row["packet_sha256"] == first.packet_sha256
        assert row["packet"]["candidate"]["counts"]["hashed"] == 1
        assert row["packet"]["preview"]["counts"]["unchanged"] == 1
        assert row["packet"]["publishable"] is False
        assert conn.execute(
            "SELECT count(*) AS n FROM brain_fileos_absence_events WHERE source_id=%s",
            (source_id,),
        ).fetchone()["n"] == 0

    metadata_packet = build_fileos_transition_review_packet(
        core, ctx, prior, first_run, tmp_path,
        source_id=source_id, observed_at=observed + timedelta(hours=1),
        metadata_only=True,
    )
    assert metadata_packet["candidate"]["deferred"][0]["reason"] == "no_hash"
    assert "version_id" not in metadata_packet["candidate"]["deferred"][0]
    metadata_record = core.stage_fileos_transition_review(
        ctx, prior, first_run, uuid4(), metadata_packet
    )
    assert metadata_record.recorded is True
    metadata_detail = core.fileos_transition_review(
        detail_ctx, metadata_record.packet_id, include_details=True
    )
    deferred = [row for row in metadata_detail["details"] if row["ledger"] == "deferred"]
    assert len(deferred) == 1 and deferred[0]["reason"] == "no_hash"
    assert "sha256" not in deferred[0] and "version_id" not in deferred[0]
    with pytest.raises(Conflict, match="already recorded"):
        core.stage_fileos_transition_review(ctx, prior, first_run, uuid4(), metadata_packet)
    tampered = dict(metadata_packet)
    tampered["publishable"] = True
    with pytest.raises(ValueError, match="binding"):
        core.stage_fileos_transition_review(ctx, prior, first_run, uuid4(), tampered)
    forged_counts = json.loads(json.dumps(metadata_packet))
    forged_counts["candidate"]["counts"]["deferred"] = 0
    forged_counts["preview"]["candidate_counts"]["deferred"] = 0
    with pytest.raises(ValueError, match="ledger"):
        core.stage_fileos_transition_review(ctx, prior, first_run, uuid4(), forged_counts)
    invented_digest = json.loads(json.dumps(metadata_packet))
    invented_digest["candidate"]["deferred"][0]["version_id"] = "invented"
    with pytest.raises(ValueError, match="ledger"):
        core.stage_fileos_transition_review(ctx, prior, first_run, uuid4(), invented_digest)
    oversized = dict(metadata_packet)
    oversized["candidate"] = dict(metadata_packet["candidate"])
    oversized["candidate"]["extra"] = "x" * (16 * 1024 * 1024)
    with pytest.raises(ValueError, match="byte bound"):
        core.stage_fileos_transition_review(ctx, prior, first_run, uuid4(), oversized)

    second = fileos_manifest(tmp_path, source_id=source_id, hour=2)
    second_run = uuid4()
    core.import_fileos_snapshot(ctx, second, second_run)
    core.complete_fileos_run(
        ctx, second, second_run,
        outcomes={"unsupported": 1},
        item_outcomes={second["items"][0]["item_id"]: "unsupported"},
        published_documents=0,
        code_revision="test-packet-v1",
        document_processor_version=None,
    )
    with pytest.raises(Conflict, match="baseline requires review"):
        core.stage_fileos_transition_review(ctx, prior, first_run, uuid4(), metadata_packet)
    assert core.fileos_transition_review(ctx, packet_id)["latest_receipt_matches_packet"] is False
    with psycopg.connect(admin) as conn:
        with pytest.raises(psycopg.Error, match="protected record"):
            conn.execute("TRUNCATE brain_fileos_transition_packets")
    with psycopg.connect(admin) as conn:
        conn.execute("ALTER TABLE brain_fileos_transition_packets DISABLE TRIGGER immutable")
        conn.execute(
            "UPDATE brain_fileos_transition_packets SET packet_sha256=%s WHERE id=%s",
            ("0" * 64, packet_id),
        )
        conn.execute("ALTER TABLE brain_fileos_transition_packets ENABLE TRIGGER immutable")
    with pytest.raises(Conflict, match="integrity requires review"):
        core.fileos_transition_review(ctx, packet_id)
    assert proof.read_bytes() == b"fictional immutable packet proof"
