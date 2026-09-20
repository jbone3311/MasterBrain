"""Real PostgreSQL tests. Only run against a disposable database named email_brain_test*.

CI supplies the database; no real credentials/accounts/mailboxes are involved.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import replace
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from email_brain.domain.models import TenantContext
from email_brain.migrate import grant_runtime, migrate
from email_brain.schemas import FeaturePayload, ProposalRequest, ReviewRequest, SearchRequest
from email_brain.store import AccessDenied, Conflict, IngestItem, NotFound, Store

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


def item(key: str = "e1", body: str = "Melron investment briefing") -> IngestItem:
    return IngestItem(
        key,
        "provider-message-1",
        key,
        datetime(2026, 9, 19, tzinfo=UTC),
        f"From: alex@example.invalid\r\nSubject: Melron\r\n\r\n{body}".encode(),
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
