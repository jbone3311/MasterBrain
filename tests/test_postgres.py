"""Real PostgreSQL tests. Only run against a disposable database named email_brain_test*.

CI supplies the database; no real credentials/accounts/mailboxes are involved.
"""

from __future__ import annotations

import hashlib
import os
import secrets
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from typing import Any
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
from email_brain.migrate import grant_runtime, migrate
from email_brain.schemas import FeaturePayload, ProposalRequest, ReviewRequest, SearchRequest
from email_brain.store import AccessDenied, Conflict, IngestItem, InventoryError, NotFound, Store
from email_brain.sync import Checkpoint, ReadWorker
from email_brain.sync_store import SyncStore
from email_brain.synthetic import fake_email
from masterbrain.datacore.extraction import ExtractionStatus, FileOSAdapter
from masterbrain.datacore.fileos import snapshot_tree
from masterbrain.datacore.persistence import DataCoreStore

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


def fileos_manifest(root: Path, *, source_id: str = "files_test", hour: int = 1) -> dict[str, Any]:
    return snapshot_tree(
        root,
        source_id=source_id,
        observed_at=datetime(2026, 9, 22, hour, tzinfo=UTC),
    )


def datacore_context(ctx: TenantContext) -> TenantContext:
    return replace(
        ctx,
        scopes=ctx.scopes
        | frozenset({"brain.source.ingest", "brain.document.publish", "brain.search"}),
    )


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


def test_fileos_adapter_isolates_sibling_failure_and_publishes_searchable_text(
    database: tuple[Store, str], tenant: tuple[TenantContext, UUID], tmp_path: Path
) -> None:
    store, _ = database
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

    result = FileOSAdapter(DataCoreStore(store)).publish_snapshot(
        ctx,
        tmp_path,
        manifest,
        uuid4(),
        code_revision="test-adapter-v1",
    )
    assert result.counts == {"changed": 1, "extracted": 1, "unsupported": 1}
    by_name = {entry.extraction.locator: entry for entry in result.results}
    assert by_name["good.txt"].publication is not None
    assert by_name["changed.txt"].extraction.status is ExtractionStatus.CHANGED
    assert by_name["image.bin"].extraction.status is ExtractionStatus.UNSUPPORTED
    hits = DataCoreStore(store).search(ctx, "searchable source")
    assert len(hits) == 1 and hits[0].locator == "good.txt"


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
