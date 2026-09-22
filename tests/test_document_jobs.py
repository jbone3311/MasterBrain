"""Real SQL source-to-search and adversarial document approval tests; synthetic only."""

import hashlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from threading import Event
from unittest.mock import Mock
from uuid import UUID, uuid4

import psycopg
import pytest
import test_postgres as pg
from fastapi.testclient import TestClient
from pdf_samples import mail_packet, variant
from psycopg import sql
from psycopg.types.json import Jsonb
from test_recovery_jobs import worker_principal

from email_brain.api import create_app
from email_brain.auth import Credential, Principal, TokenRegistry
from email_brain.document_jobs import POLICY, DocumentJobs
from email_brain.pdf_contract import PdfPage, PdfResult, PdfUnavailable, source_for
from email_brain.schemas import SearchRequest
from email_brain.store import AccessDenied, Conflict, NotFound
from masterbrain.datacore.persistence import DataCoreStore

database, tenant = pg.database, pg.tenant
pytestmark = pytest.mark.postgres
VERSION = "sandbox-pdf-v1-" + "a" * 64


class FakePdf:
    processor_version = VERSION

    def extract(self, raw, *, part_path, part_sha256):
        return PdfResult(
            source_for(raw, part_path, part_sha256),
            "extracted",
            "bounded_pdf_v1",
            1,
            (PdfPage(1, "pdfonlyproof fictional document"),),
        )


def ready(store, ctx, account):
    raw, _, _ = mail_packet(variant("text"))
    store.ingest_page(ctx, account, None, "document-ready", [replace(pg.item(), raw=raw)])
    with store.transaction(ctx) as conn:
        return conn.execute(
            "SELECT id FROM attachment_receipts WHERE account_id=%s", (account,)
        ).fetchone()["id"]


def setup(database, tenant):
    store, admin = database
    ctx, account = tenant
    receipt = ready(store, ctx, account)
    jobs, human = DocumentJobs(store, VERSION), Principal(ctx, "human")
    base = worker_principal(admin, ctx)
    worker = replace(
        base, context=replace(base.context, scopes=frozenset({"email.document.process"}))
    )
    job = jobs.enqueue(human, account, receipt, VERSION, POLICY, uuid4())
    return jobs, human, worker, receipt, job


def snapshot(store, ctx):
    with store.transaction(ctx) as conn:
        return {
            table: conn.execute(
                sql.SQL("SELECT * FROM {} ORDER BY 1").format(sql.Identifier(table))
            ).fetchall()
            for table in (
                "messages",
                "message_versions",
                "attachment_receipts",
                "raw_objects",
                "sync_cursors",
                "provider_events",
                "message_sync_state",
                "intake_events",
            )
        }


def expire(admin, job, column="lease_until"):
    with psycopg.connect(admin) as conn:
        conn.execute("SET LOCAL session_replication_role=replica")
        if column == "expires_at":
            conn.execute(
                "UPDATE document_jobs SET created_at=statement_timestamp()-interval '2 hours',"
                "expires_at=statement_timestamp()-interval '1 hour' WHERE id=%s",
                (job,),
            )
        else:
            assert column in {"lease_until", "retry_at"}
            conn.execute(
                sql.SQL(
                    "UPDATE document_jobs SET {}=clock_timestamp()-interval '1 second' WHERE id=%s"
                ).format(sql.Identifier(column)),
                (job,),
            )


def assert_no_result(store, ctx):
    with store.transaction(ctx) as conn:
        assert conn.execute("SELECT count(*) AS n FROM document_extractions").fetchone()["n"] == 0
    assert store.search(ctx, SearchRequest(query="pdfonlyproof", include_documents=True)) == []


def test_approved_result_search_citation_cache_and_unchanged_source(database, tenant):
    store, _ = database
    ctx, account = tenant
    jobs, human, worker, receipt, job = setup(database, tenant)
    before = snapshot(store, ctx)
    assert_no_result(store, ctx)
    processor = FakePdf()
    processor.extract = Mock(wraps=processor.extract)
    result = jobs.run_once(worker, account, processor)
    assert result["status"] == "completed" and result["outcome"] == "result_saved"
    assert snapshot(store, ctx) == before
    assert store.search(ctx, SearchRequest(query="pdfonlyproof")) == []
    hits = store.search(ctx, SearchRequest(query="pdfonlyproof", include_documents=True))
    assert len(hits) == 1 and hits[0]["result_type"] == "document"
    assert hits[0]["scanner_status"] == "unscanned" and hits[0]["revision"] == 1
    evidence = store.document_evidence(ctx, result["extraction_id"])
    assert evidence["citation"] == hits[0]["citation"]
    assert "pdfonlyproof" in evidence["pages"][0]["excerpt"]
    assert evidence["untrusted_content"] and evidence["receipt_id"] == receipt
    second = jobs.enqueue(human, account, receipt, VERSION, POLICY, uuid4())
    assert jobs.run_once(worker, account, processor)["extraction_id"] == result["extraction_id"]
    assert processor.extract.call_count == 1
    assert jobs.get(ctx, account, second["id"])["status"] == "completed"
    assert jobs.cancel(human, account, job["id"])["status"] == "completed"
    assert jobs.run_once(worker, account, processor) is None


def test_approved_pdf_derivative_bridge_replay_rls_and_immutability(database, tenant):
    store, admin = database
    ctx, account = tenant
    jobs, _, worker, receipt, _ = setup(database, tenant)
    completed = jobs.run_once(worker, account, FakePdf())
    extraction_id = completed["extraction_id"]
    assert completed["status"] == "completed" and extraction_id is not None
    bridge_ctx = pg.datacore_context(ctx)
    core = DataCoreStore(store)
    with store.transaction(ctx) as conn:
        parent_id = conn.execute(
            "SELECT evidence_id FROM attachment_receipts WHERE id=%s", (receipt,)
        ).fetchone()["evidence_id"]
    core.bridge_current_email_version(
        bridge_ctx, parent_id, uuid4(), code_revision="pdf-derivative-test-v1"
    )
    with pytest.raises(Conflict, match="bridged current attachment"):
        core.bridge_email_document_extraction(
            bridge_ctx, extraction_id, uuid4(), code_revision="pdf-derivative-test-v1"
        )
    assert core.search(bridge_ctx, "pdfonlyproof") == []

    attachment = core.bridge_email_attachment(
        bridge_ctx, receipt, uuid4(), code_revision="pdf-derivative-test-v1"
    )
    derived = core.bridge_email_document_extraction(
        bridge_ctx, extraction_id, uuid4(), code_revision="pdf-derivative-test-v1"
    )
    assert derived.changed is True
    assert derived.evidence_id == attachment.evidence_id
    assert derived.extraction_status == "extracted" and derived.chunks == 1
    assert [hit.evidence_id for hit in core.search(bridge_ctx, "pdfonlyproof")] == [
        attachment.evidence_id
    ]
    replay = core.bridge_email_document_extraction(
        bridge_ctx, extraction_id, uuid4(), code_revision="pdf-derivative-test-v1"
    )
    assert replay == replace(derived, changed=False)

    with store.transaction(bridge_ctx) as conn:
        saved = conn.execute(
            "SELECT legacy_attachment_id,legacy_extraction_id,legacy_approval_job_id,"
            "extraction_status,result_sha256,chunk_count FROM "
            "brain_email_document_bridge_receipts"
        ).fetchone()
        assert saved["legacy_attachment_id"] == receipt
        assert saved["legacy_extraction_id"] == extraction_id
        assert saved["legacy_approval_job_id"] == completed["id"]
        assert saved["extraction_status"] == "extracted"
        assert len(saved["result_sha256"]) == 64 and saved["chunk_count"] == 1
    other_tenant, other_actor = uuid4(), uuid4()
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO tenants(id,name) VALUES (%s,'Document bridge other')",
            (other_tenant,),
        )
        conn.execute(
            "INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES (%s,%s,'owner')",
            (other_tenant, other_actor),
        )
    other = replace(
        bridge_ctx,
        tenant_id=other_tenant,
        actor_id=other_actor,
        request_id=uuid4(),
        identity=None,
    )
    with store.transaction(other) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM brain_email_document_bridge_receipts"
        ).fetchone()["n"] == 0
    with pytest.raises(psycopg.errors.RaiseException), psycopg.connect(admin) as conn:
        conn.execute(
            "UPDATE brain_email_document_bridge_receipts SET code_revision='rewritten' "
            "WHERE tenant_id=%s",
            (ctx.tenant_id,),
        )


def test_unapproved_pdf_extraction_cannot_bridge(database, tenant):
    store, admin = database
    ctx, account = tenant
    receipt = ready(store, ctx, account)
    bridge_ctx = pg.datacore_context(ctx)
    core = DataCoreStore(store)
    with store.transaction(ctx) as conn:
        source = conn.execute(
            "SELECT a.evidence_id,a.part_id,a.sha256,v.raw_sha256 FROM attachment_receipts a "
            "JOIN message_versions v ON v.tenant_id=a.tenant_id "
            "AND v.account_id=a.account_id AND v.id=a.evidence_id WHERE a.id=%s",
            (receipt,),
        ).fetchone()
    core.bridge_current_email_version(
        bridge_ctx,
        source["evidence_id"],
        uuid4(),
        code_revision="unapproved-pdf-test-v1",
    )
    core.bridge_email_attachment(
        bridge_ctx, receipt, uuid4(), code_revision="unapproved-pdf-test-v1"
    )
    payload = {
        "contract_version": "sandbox-pdf-v1",
        "source": {
            "raw_sha256": source["raw_sha256"],
            "part_path": source["part_id"],
            "part_sha256": source["sha256"],
        },
        "status": "extracted",
        "reason": "bounded_pdf_v1",
        "page_count": 1,
        "pages": [{"number": 1, "text": "unapproved fictional result"}],
        "scanner_status": "unscanned",
    }
    extraction_id = uuid4()
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO document_extractions(id,tenant_id,account_id,receipt_id,"
            "processor_version,policy_version,revision,result) "
            "VALUES (%s,%s,%s,%s,%s,%s,1,%s)",
            (extraction_id, ctx.tenant_id, account, receipt, VERSION, POLICY, Jsonb(payload)),
        )
    with pytest.raises(Conflict, match="not approved"):
        core.bridge_email_document_extraction(
            bridge_ctx, extraction_id, uuid4(), code_revision="unapproved-pdf-test-v1"
        )
    with store.transaction(bridge_ctx) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM brain_email_document_bridge_receipts"
        ).fetchone()["n"] == 0


def test_enqueue_idempotency_race_and_account_history(database, tenant):
    store, _ = database
    ctx, account = tenant
    jobs, human, _, receipt, first = setup(database, tenant)
    key = uuid4()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: jobs.enqueue(human, account, receipt, VERSION, POLICY, key), range(2)
            )
        )
    assert results[0]["id"] == results[1]["id"]
    with pytest.raises(Conflict):
        jobs.enqueue(human, account, uuid4(), VERSION, POLICY, key)
    page = jobs.list(ctx, account, limit=1)
    assert page["next_after"] == results[0]["id"]
    assert jobs.list(ctx, account, after=page["next_after"])["results"][0]["id"] == first["id"]
    with pytest.raises(NotFound):
        jobs.list(ctx, account, after=uuid4())
    assert {"lease_token", "source_event_key", "worker_actor_id", "actor_id"}.isdisjoint(results[0])


@pytest.mark.parametrize(
    "kind,scopes",
    [
        ("assistant", {"email.review", "email.evidence.read"}),
        ("worker", {"email.review", "email.evidence.read"}),
        ("human", {"email.review"}),
        ("human", {"email.evidence.read"}),
    ],
)
def test_human_both_scopes_required(database, tenant, kind, scopes):
    jobs, human, _, receipt, job = setup(database, tenant)
    principal = replace(
        human, client_kind=kind, context=replace(human.context, scopes=frozenset(scopes))
    )
    with pytest.raises(AccessDenied):
        jobs.enqueue(principal, tenant[1], receipt, VERSION, POLICY, uuid4())
    with pytest.raises(AccessDenied):
        jobs.cancel(principal, tenant[1], job["id"])


@pytest.mark.parametrize(
    "kind,scopes",
    [("human", {"email.document.process"}), ("worker", {"email.process"}), ("worker", set())],
)
def test_worker_permission_separate(database, tenant, kind, scopes):
    jobs, _, worker, _, _ = setup(database, tenant)
    with pytest.raises(AccessDenied):
        jobs.run_once(
            replace(
                worker, client_kind=kind, context=replace(worker.context, scopes=frozenset(scopes))
            ),
            tenant[1],
            FakePdf(),
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "cancel",
        "owner",
        "worker",
        "account",
        "enroll",
        "source",
        "delete",
        "lease",
        "approval",
        "version",
        "hash",
    ],
)
def test_changes_during_processing_fence_publication(database, tenant, monkeypatch, mutation):
    store, admin = database
    ctx, account = tenant
    jobs, human, worker, _, job = setup(database, tenant)
    processor = FakePdf()
    extract = processor.extract
    changed_state = []

    def changed(raw, **kw):
        result = extract(raw, **kw)
        if mutation == "cancel":
            jobs.cancel(human, account, job["id"])
        elif mutation in {"lease", "approval"}:
            expire(admin, job["id"], "expires_at" if mutation == "approval" else "lease_until")
        elif mutation == "version":
            processor.processor_version = "sandbox-pdf-v1-" + "b" * 64
        elif mutation == "hash":
            result = replace(result, source=replace(result.source, part_sha256="b" * 64))
        elif mutation in {"source", "delete"}:
            store.ingest_page(
                ctx,
                account,
                "document-ready",
                "changed",
                [replace(pg.item("changed"), raw=None if mutation == "delete" else raw)],
            )
        else:
            with psycopg.connect(admin) as conn:
                if mutation in {"owner", "worker"}:
                    conn.execute(
                        "DELETE FROM tenant_memberships WHERE tenant_id=%s AND user_id=%s",
                        (
                            ctx.tenant_id,
                            ctx.actor_id if mutation == "owner" else worker.context.actor_id,
                        ),
                    )
                elif mutation == "account":
                    conn.execute("UPDATE mail_accounts SET status='paused' WHERE id=%s", (account,))
                elif mutation == "enroll":
                    conn.execute(
                        "UPDATE mail_accounts SET provider_account_id='new-binding' WHERE id=%s",
                        (account,),
                    )
                else:
                    raise AssertionError("unknown mutation")
        changed_state.append(mutation)
        return result

    monkeypatch.setattr(processor, "extract", changed)
    jobs.run_once(worker, account, processor)
    assert changed_state == [mutation], "fault setup must succeed rather than become a parser error"
    with psycopg.connect(admin) as conn:
        expected = {
            "cancel": "cancelled",
            "owner": "revoked",
            "worker": "running",
            "account": "revoked",
            "enroll": "stale",
            "source": "stale",
            "delete": "stale",
            "lease": "running",
            "approval": "expired",
            "version": "retry_wait",
            "hash": "retry_wait",
        }
        assert (
            conn.execute("SELECT status FROM document_jobs WHERE id=%s", (job["id"],)).fetchone()[0]
            == expected[mutation]
        )
        assert (
            conn.execute(
                "SELECT count(*) FROM document_extractions WHERE tenant_id=%s", (ctx.tenant_id,)
            ).fetchone()[0]
            == 0
        )
    if mutation not in {"owner", "worker"}:
        assert_no_result(store, ctx)


def test_cancel_between_source_loading_and_disclosure(database, tenant, monkeypatch):
    store, _ = database
    jobs, human, worker, _, job = setup(database, tenant)
    original = store.load_raw

    def load(*args):
        raw = original(*args)
        jobs.cancel(human, tenant[1], job["id"])
        return raw

    monkeypatch.setattr(store, "load_raw", load)
    processor = FakePdf()
    processor.extract = Mock(side_effect=AssertionError("must not disclose"))
    assert jobs.run_once(worker, tenant[1], processor)["status"] == "cancelled"
    processor.extract.assert_not_called()


def test_single_claim_and_cancel_while_parser_unlocked(database, tenant):
    jobs, human, worker, _, job = setup(database, tenant)
    entered, release = Event(), Event()
    processor = FakePdf()
    original = processor.extract

    def slow(raw, **kw):
        entered.set()
        assert release.wait(10)
        return original(raw, **kw)

    processor.extract = slow
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(jobs.run_once, worker, tenant[1], processor)
        try:
            assert entered.wait(10)
            assert jobs.run_once(worker, tenant[1], FakePdf()) is None
            assert jobs.cancel(human, tenant[1], job["id"])["status"] == "cancelled"
        finally:
            release.set()
        assert pending.result(timeout=10)["status"] == "cancelled"
    assert_no_result(database[0], tenant[0])


def test_bounded_retry_and_process_recreation(database, tenant):
    store, admin = database
    jobs, _, worker, _, job = setup(database, tenant)
    processor = FakePdf()
    processor.extract = Mock(side_effect=PdfUnavailable())
    for attempt in range(1, 4):
        output = DocumentJobs(store, VERSION).run_once(worker, tenant[1], processor)
        assert output["attempts"] == attempt
        assert output["status"] == ("retry_wait" if attempt < 3 else "failed")
        assert_no_result(store, tenant[0])
        if attempt < 3:
            assert jobs.run_once(worker, tenant[1], processor) is None
            expire(admin, job["id"], "retry_at")
    assert jobs.run_once(worker, tenant[1], processor) is None


def test_crash_lease_replacement_and_expired_approval(database, tenant):
    jobs, human, worker, receipt, job = setup(database, tenant)
    first = jobs._claim(worker.context, tenant[1])
    expire(database[1], job["id"])
    second = jobs._claim(worker.context, tenant[1])
    assert second["lease_token"] != first["lease_token"] and second["attempts"] == 2
    assert jobs._failed(worker.context, first)["status"] == "running"
    expire(database[1], job["id"])
    assert jobs.run_once(worker, tenant[1], FakePdf())["status"] == "completed"
    other = jobs.enqueue(human, tenant[1], receipt, VERSION, POLICY, uuid4())
    expire(database[1], other["id"], "expires_at")
    assert jobs.run_once(worker, tenant[1], FakePdf())["status"] == "expired"


@pytest.mark.parametrize(
    "status,reason,pages",
    [
        ("deferred", "encrypted", ()),
        ("failed", "invalid_pdf", ()),
        ("partial", "pages_without_text", (PdfPage(1, "pdfonlyproof"), PdfPage(2, ""))),
    ],
)
def test_explicit_outcomes_and_latest_revision_hides_older_text(
    database, tenant, status, reason, pages
):
    store, _ = database
    ctx, account = tenant
    jobs, human, worker, receipt, _ = setup(database, tenant)
    first = jobs.run_once(worker, account, FakePdf())
    processor = FakePdf()
    processor.processor_version = "sandbox-pdf-v1-" + "b" * 64
    processor.extract = lambda raw, **kw: PdfResult(
        source_for(raw, kw["part_path"], kw["part_sha256"]),
        status,
        reason,
        len(pages) or None,
        pages,
    )
    newer = DocumentJobs(store, processor.processor_version)
    newer.enqueue(human, account, receipt, processor.processor_version, POLICY, uuid4())
    second = newer.run_once(worker, account, processor)
    evidence = store.document_evidence(ctx, second["extraction_id"])
    assert evidence["revision"] == 2 and evidence["status"] == status
    assert store.document_evidence(ctx, first["extraction_id"])["status"] == "extracted"
    hits = store.search(ctx, SearchRequest(query="pdfonlyproof", include_documents=True))
    assert len(hits) == (1 if pages else 0)
    if hits:
        assert hits[0]["document_id"] == second["extraction_id"]


def test_publication_rolls_back_if_audit_fails(database, tenant, monkeypatch):
    store, _ = database
    jobs, _, worker, _, _ = setup(database, tenant)
    original = store.audit

    def audit(conn, ctx, event, *args):
        if event == "document.job_completed":
            raise RuntimeError("synthetic completion failure")
        return original(conn, ctx, event, *args)

    monkeypatch.setattr(store, "audit", audit)
    assert jobs.run_once(worker, tenant[1], FakePdf())["status"] == "retry_wait"
    assert_no_result(store, tenant[0])


def test_foreign_access_and_immutable_results(database, tenant):
    store, admin = database
    ctx, account = tenant
    jobs, human, worker, receipt, job = setup(database, tenant)
    completed = jobs.run_once(worker, account, FakePdf())
    foreign = pg.tenant.__wrapped__(database)
    for call in (
        lambda: jobs.get(foreign[0], account, job["id"]),
        lambda: jobs.list(foreign[0], account),
        lambda: jobs.cancel(Principal(foreign[0], "human"), account, job["id"]),
        lambda: store.document_evidence(foreign[0], completed["extraction_id"]),
    ):
        with pytest.raises(NotFound):
            call()
    assert (
        store.search(foreign[0], SearchRequest(query="pdfonlyproof", include_documents=True)) == []
    )
    assert (
        store.search(
            ctx, SearchRequest(query="pdfonlyproof", account_id=foreign[1], include_documents=True)
        )
        == []
    )
    for statement, identity in (
        ("UPDATE attachment_receipts SET part_id='1.99' WHERE id=%s", receipt),
        ("UPDATE document_jobs SET processor_version=%s WHERE id=%s", job["id"]),
        ("DELETE FROM document_extractions WHERE id=%s", completed["extraction_id"]),
    ):
        with psycopg.connect(admin) as conn, pytest.raises(psycopg.Error):
            args = (
                (VERSION.replace("a", "b"), identity)
                if "processor_version" in statement
                else (identity,)
            )
            conn.execute(statement, args)
    with store.transaction(ctx) as conn, pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(
            "UPDATE document_extractions SET revision=99 WHERE id=%s", (completed["extraction_id"],)
        )
    assert jobs.cancel(human, account, job["id"])["status"] == "completed"


def client(store, ctx, *, kind="human", scopes=None, version=VERSION):
    token = "synthetic-document-token-" + "x" * 32
    credential = Credential(
        token_sha256=hashlib.sha256(token.encode()).hexdigest(),
        tenant_id=ctx.tenant_id,
        actor_id=ctx.actor_id,
        scopes=set(scopes if scopes is not None else ctx.scopes),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        client_kind=kind,
    )
    result = TestClient(
        create_app(store, TokenRegistry([credential]), document_processor_version=version)
    )
    result.headers["Authorization"] = "Bearer " + token
    return result


def test_rest_approval_result_search_history_and_validation(database, tenant):
    store, _ = database
    ctx, account = tenant
    jobs, _, worker, receipt, old = setup(database, tenant)
    api = client(store, ctx)
    route = f"/v1/accounts/{account}/attachments/{receipt}/jobs"
    body = {"expected_processor_version": VERSION, "policy_version": POLICY}
    headers = {"Idempotency-Key": str(uuid4())}
    assert api.get(f"/v1/accounts/{account}/documents").json()["enabled"]
    assert api.post(route, json=body).status_code == 422
    assert api.post(route, json={**body, "image": "arbitrary"}, headers=headers).status_code == 422
    assert api.post(route, json=body, headers=headers).status_code == 202
    jobs.cancel(Principal(ctx, "human"), account, old["id"])
    done = jobs.run_once(worker, account, FakePdf())
    assert api.get(f"/v1/documents/{done['extraction_id']}").json()["scanner_status"] == "unscanned"
    assert api.post("/v1/search", json={"query": "pdfonlyproof", "include_documents": True}).json()[
        "results"
    ][0]["document_id"] == str(done["extraction_id"])
    assert len(api.get(f"/v1/accounts/{account}/documents/jobs").json()["results"]) == 2
    assert api.get(f"/v1/accounts/{account}/documents/jobs?limit=51").status_code == 422
    assert (
        api.post(f"/v1/accounts/{account}/documents/jobs/{done['id']}/cancel").json()["status"]
        == "completed"
    )
    assert api.get(f"/v1/accounts/{account}/documents/jobs/{done['id']}").status_code == 200
    assert (
        client(store, ctx, version=None).post(route, json=body, headers=headers).status_code == 409
    )
    assert (
        client(store, ctx, kind="assistant", scopes={"email.evidence.read"})
        .post(route, json=body, headers=headers)
        .status_code
        == 403
    )
    assert api.post(f"/v1/accounts/{account}/documents/execute").status_code == 404
    assert UUID(done["id"].hex) == done["id"]


def test_cached_result_still_requires_current_owner_and_eligible_source(database, tenant):
    store, admin = database
    ctx, account = tenant
    jobs, human, worker, receipt, _ = setup(database, tenant)
    jobs.run_once(worker, account, FakePdf())
    jobs.enqueue(human, account, receipt, VERSION, POLICY, uuid4())
    with psycopg.connect(admin) as conn:
        conn.execute(
            "DELETE FROM tenant_memberships WHERE tenant_id=%s AND user_id=%s",
            (ctx.tenant_id, ctx.actor_id),
        )
    processor = FakePdf()
    processor.extract = Mock(side_effect=AssertionError("must not process"))
    assert jobs.run_once(worker, account, processor)["status"] == "revoked"
    processor.extract.assert_not_called()
    with psycopg.connect(admin) as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM document_extractions WHERE tenant_id=%s", (ctx.tenant_id,)
            ).fetchone()[0]
            == 1
        )


def test_unfinished_queue_limit_and_same_tenant_account_boundaries(database, tenant):
    store, admin = database
    ctx, account = tenant
    jobs, human, _, receipt, first = setup(database, tenant)
    for _ in range(99):
        jobs.enqueue(human, account, receipt, VERSION, POLICY, uuid4())
    with pytest.raises(Conflict, match="queue"):
        jobs.enqueue(human, account, receipt, VERSION, POLICY, uuid4())
    other = uuid4()
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO mail_accounts(id,tenant_id,provider,address,secret_ref) "
            "VALUES (%s,%s,'fastmail','other@example.invalid','synthetic:none')",
            (other, ctx.tenant_id),
        )
    for call in (
        lambda: jobs.get(ctx, other, first["id"]),
        lambda: jobs.list(ctx, other, after=first["id"]),
        lambda: jobs.enqueue(human, other, receipt, VERSION, POLICY, uuid4()),
    ):
        with pytest.raises(NotFound):
            call()


def test_document_page_excerpt_bound_and_missing_scope(database, tenant):
    store, _ = database
    ctx, account = tenant
    jobs, _, worker, _, _ = setup(database, tenant)
    processor = FakePdf()
    original = processor.extract
    processor.extract = lambda raw, **kw: replace(
        original(raw, **kw), pages=(PdfPage(1, "x" * 3000),)
    )
    done = jobs.run_once(worker, account, processor)
    page = store.document_evidence(ctx, done["extraction_id"])["pages"][0]
    assert len(page["excerpt"]) == 2000 and page["truncated"] and page["offsets"] == [0, 2000]
    assert page["excerpt_sha256"] == hashlib.sha256(page["excerpt"].encode()).hexdigest()
    with pytest.raises(AccessDenied):
        store.document_evidence(
            replace(ctx, scopes=frozenset({"email.search"})), done["extraction_id"]
        )
