"""Fictional current Email attachment PDF review-to-retained-MIME receipt."""

from __future__ import annotations

import hashlib
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event
from uuid import uuid4

import psycopg
import pytest
import test_postgres as pg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from test_document_jobs import VERSION, setup
from test_recovery_jobs import worker_principal
from test_sandbox_runner import IMAGE, fake_docker

from email_brain.auth import Principal
from email_brain.document_jobs import POLICY, DocumentJobs
from email_brain.migrate import grant_tenant_runtime
from email_brain.pdf_contract import encode_request
from email_brain.pdf_processor import DockerPdfProcessor
from email_brain.pdf_worker import process_request
from email_brain.store import AccessDenied, Conflict, NotFound, Store
from masterbrain import source_tier_email_pdf_replay as replay_module
from masterbrain.datacore.persistence import DataCoreStore
from masterbrain.knowledge_schema import SourceTierReviewWrite
from masterbrain.source_tier_email_pdf_replay import SourceTierEmailPdfReplayStore
from masterbrain.source_tier_reviews import SourceTierReviews

pytestmark = pytest.mark.postgres
database, tenant = pg.database, pg.tenant


def _worker(ctx: pg.TenantContext) -> pg.TenantContext:
    return replace(
        ctx, scopes=frozenset({"brain.document.publish", "email.evidence.read"}),
    )


def _prepared(database, tenant, monkeypatch: pytest.MonkeyPatch):
    store, admin = database
    ctx, account = tenant
    jobs, _, job_worker, receipt_id, _ = setup(database, tenant)
    with store.transaction(ctx) as conn:
        attachment = conn.execute(
            "SELECT a.part_id,a.sha256,a.evidence_id,v.raw_sha256 "
            "FROM attachment_receipts a JOIN message_versions v "
            "ON v.tenant_id=a.tenant_id AND v.id=a.evidence_id WHERE a.id=%s",
            (receipt_id,),
        ).fetchone()
    raw = store.load_raw(ctx, account, attachment["raw_sha256"])
    request = encode_request(raw, attachment["part_id"], attachment["sha256"])
    output = process_request(request)
    processor, _, _ = fake_docker(
        monkeypatch, processor=DockerPdfProcessor(IMAGE), output=output,
    )
    completed = jobs.run_once(job_worker, account, processor)
    assert completed is not None and completed["status"] == "completed"
    extraction_id = completed["extraction_id"]
    assert extraction_id is not None
    core = DataCoreStore(store)
    bridge_ctx = pg.datacore_context(ctx)
    core.bridge_current_email_version(
        bridge_ctx, attachment["evidence_id"], uuid4(),
        code_revision="email-pdf-tier-test-v1",
    )
    core.bridge_email_attachment(
        bridge_ctx, receipt_id, uuid4(), code_revision="email-pdf-tier-test-v1",
    )
    derived = core.bridge_email_document_extraction(
        bridge_ctx, extraction_id, uuid4(), code_revision="email-pdf-tier-test-v1",
    )
    reviewer = replace(
        ctx, scopes=ctx.scopes | frozenset({"knowledge.review", "brain.content.read"}),
    )
    with store.transaction(reviewer) as conn:
        row = conn.execute(
            "SELECT d.evidence_id,d.body_sha256,e.source_version_id,e.sha256 "
            "FROM brain_normalized_documents d JOIN brain_evidence e "
            "ON e.tenant_id=d.tenant_id AND e.id=d.evidence_id WHERE d.id=%s",
            (derived.document_id,),
        ).fetchone()
    assert row is not None
    review = SourceTierReviewWrite(
        evidence_id=row["evidence_id"], document_id=derived.document_id,
        document_sha256=row["body_sha256"],
        source_version_id=row["source_version_id"], source_sha256=row["sha256"],
        source_tier="T3", authority_kind="internal_record",
        source_quote="pdfonlyproof",
    )
    review_id = SourceTierReviews(store).publish(
        reviewer, row["evidence_id"], review, uuid4(),
    )["object_id"]
    # The isolated pipe is one-shot; the replay receives a fresh exact pipe.
    fake_docker(monkeypatch, processor=processor, output=output)
    role = "test_pdf_receipt_" + uuid4().hex[:12]
    password = secrets.token_urlsafe(32)
    with psycopg.connect(admin) as conn:
        conn.execute(
            sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD {}").format(
                sql.Identifier(role), sql.Literal(password),
            ),
        )
        grant_tenant_runtime(conn, role, ctx.tenant_id)
    bound_store = Store(
        make_conninfo(admin, user=role, password=password),
        tenant_dsns={ctx.tenant_id: make_conninfo(admin, user=role, password=password)},
    )
    return bound_store, admin, ctx, account, raw, processor, review_id, receipt_id


def test_current_reviewed_attachment_replays_exact_mime_and_is_immutable(
    database, tenant, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, admin, ctx, account, raw, processor, review_id, _ = _prepared(
        database, tenant, monkeypatch,
    )
    replay = SourceTierEmailPdfReplayStore(store, processor)
    result = replay.record_current_pdf_replay(
        _worker(ctx), review_id, expected_account_id=account,
    )
    assert result == {
        "review_id": review_id,
        "worker_observed_pdf_text_replay": True,
        "source_effects": False,
        "financial_claim_approved": False,
    }
    with store.transaction(_worker(ctx)) as conn:
        saved = conn.execute(
            "SELECT raw_sha256,raw_size_bytes,part_path,part_sha256,"
            "part_size_bytes,text_sha256,normalizer,page_count "
            "FROM knowledge_source_tier_email_pdf_replays WHERE review_id=%s",
            (review_id,),
        ).fetchone()
        assert saved is not None
        assert saved["raw_sha256"] == hashlib.sha256(raw).hexdigest()
        assert saved["raw_size_bytes"] == len(raw)
        assert saved["part_path"] == "1.2"
        assert saved["part_sha256"] != saved["raw_sha256"]
        assert 0 < saved["part_size_bytes"] < len(raw)
        assert saved["normalizer"].startswith("email-pdf-v1:sandbox-pdf-v1-")
        assert saved["page_count"] == 1
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_claims",
        ).fetchone()["n"] == 0
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.transaction():
                conn.execute(
                    "UPDATE knowledge_source_tier_email_pdf_replays "
                    "SET page_count=2 WHERE review_id=%s", (review_id,),
                )
        with pytest.raises(psycopg.errors.RaiseException):
            with conn.transaction():
                conn.execute(
                    "INSERT INTO knowledge_source_tier_email_pdf_replays "
                    "SELECT tenant_id,review_id,evidence_id,document_id,source_version_id,"
                    "source_id,account_id,parent_version_id,legacy_attachment_id,"
                    "legacy_extraction_id,actor_id,raw_sha256,raw_size_bytes,part_path,"
                    "repeat('0',64),part_size_bytes,text_sha256,normalizer,result_sha256,"
                    "page_count,recorded_at FROM knowledge_source_tier_email_pdf_replays "
                    "WHERE review_id=%s", (review_id,),
                )
    with psycopg.connect(admin) as conn:
        with pytest.raises(psycopg.errors.RaiseException):
            with conn.transaction():
                conn.execute("TRUNCATE knowledge_source_tier_email_pdf_replays")
    fake_docker(monkeypatch, processor=processor, output=process_request(
        encode_request(raw, "1.2", saved["part_sha256"]),
    ))
    assert replay.record_current_pdf_replay(_worker(ctx), review_id) == result


def test_wrong_account_and_final_authorization_refuse_receipt(
    database, tenant, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _, ctx, _, _, processor, review_id, _ = _prepared(
        database, tenant, monkeypatch,
    )
    replay = SourceTierEmailPdfReplayStore(store, processor)
    with pytest.raises(NotFound):
        replay.record_current_pdf_replay(
            _worker(ctx), review_id, expected_account_id=uuid4(),
        )
    with pytest.raises(AccessDenied):
        replay.record_current_pdf_replay(
            _worker(ctx), review_id,
            authorize=lambda: (_ for _ in ()).throw(AccessDenied("revoked")),
        )
    with store.transaction(_worker(ctx)) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_source_tier_email_pdf_replays "
            "WHERE review_id=%s", (review_id,),
        ).fetchone()["n"] == 0


def test_changed_parent_message_refuses_before_receipt(
    database, tenant, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, admin, ctx, _, _, processor, review_id, receipt_id = _prepared(
        database, tenant, monkeypatch,
    )
    with psycopg.connect(admin) as conn:
        conn.execute(
            "UPDATE messages SET deleted=true WHERE id=("
            "SELECT v.message_id FROM attachment_receipts a JOIN message_versions v "
            "ON v.id=a.evidence_id WHERE a.id=%s)", (receipt_id,),
        )
    with pytest.raises(Conflict):
        SourceTierEmailPdfReplayStore(store, processor).record_current_pdf_replay(
            _worker(ctx), review_id,
        )
    with store.transaction(_worker(ctx)) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_source_tier_email_pdf_replays "
            "WHERE review_id=%s", (review_id,),
        ).fetchone()["n"] == 0


def test_source_grant_and_paused_source_refuse_receipt(
    database, tenant, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, admin, ctx, _, _, processor, review_id, _ = _prepared(
        database, tenant, monkeypatch,
    )
    replay = SourceTierEmailPdfReplayStore(store, processor)
    with pytest.raises(NotFound):
        replay.record_current_pdf_replay(
            replace(_worker(ctx), source_ids=frozenset({"ungranted_source"})),
            review_id,
        )
    with pytest.raises(AccessDenied):
        replay.record_current_pdf_replay(
            replace(_worker(ctx), scopes=frozenset({"email.evidence.read"})),
            review_id,
        )
    foreign = replace(_worker(ctx), tenant_id=uuid4(), actor_id=uuid4())
    with pytest.raises((AccessDenied, NotFound)):
        replay.record_current_pdf_replay(foreign, review_id)
    with psycopg.connect(admin) as conn:
        conn.execute(
            "UPDATE brain_sources SET status='paused' WHERE id=("
            "SELECT v.source_id FROM knowledge_source_tier_reviews r "
            "JOIN brain_source_versions v ON v.id=r.source_version_id "
            "WHERE r.id=%s)", (review_id,),
        )
    with pytest.raises(Conflict):
        replay.record_current_pdf_replay(_worker(ctx), review_id)
    with store.transaction(_worker(ctx)) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_source_tier_email_pdf_replays "
            "WHERE review_id=%s", (review_id,),
        ).fetchone()["n"] == 0


def test_retrospectively_excluded_parent_refuses_receipt(
    database, tenant, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, admin, ctx, account, _, processor, review_id, receipt_id = _prepared(
        database, tenant, monkeypatch,
    )
    with psycopg.connect(admin) as conn:
        conn.execute(
            "UPDATE message_sync_state SET status='excluded' "
            "WHERE tenant_id=%s AND account_id=%s AND provider_id=("
            "SELECT m.provider_message_id FROM attachment_receipts a "
            "JOIN message_versions v ON v.id=a.evidence_id "
            "JOIN messages m ON m.id=v.message_id WHERE a.id=%s)",
            (ctx.tenant_id, account, receipt_id),
        )
    with pytest.raises((Conflict, NotFound)):
        SourceTierEmailPdfReplayStore(store, processor).record_current_pdf_replay(
            _worker(ctx), review_id,
        )
    with store.transaction(_worker(ctx)) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_source_tier_email_pdf_replays "
            "WHERE review_id=%s", (review_id,),
        ).fetchone()["n"] == 0


def test_identical_pdf_in_two_messages_needs_two_independent_reviews(
    database, tenant, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, admin, ctx, account, raw, processor, first_review, first_receipt = _prepared(
        database, tenant, monkeypatch,
    )
    second_event = "fictional-pdf-second-occurrence"
    store.ingest_page(
        ctx, account, "document-ready", "document-ready-second",
        [replace(
            pg.item(second_event), provider_id="provider-message-2", raw=raw,
        )],
    )
    with store.transaction(ctx) as conn:
        second = conn.execute(
            "SELECT a.id,a.sha256,a.evidence_id,v.raw_sha256 "
            "FROM attachment_receipts a JOIN message_versions v "
            "ON v.tenant_id=a.tenant_id AND v.id=a.evidence_id "
            "JOIN messages m ON m.tenant_id=v.tenant_id AND m.id=v.message_id "
            "WHERE m.provider_message_id='provider-message-2'",
        ).fetchone()
    assert second is not None and second["id"] != first_receipt
    assert second["raw_sha256"] == hashlib.sha256(raw).hexdigest()
    jobs = DocumentJobs(store, VERSION)
    jobs.enqueue(
        Principal(ctx, "human"), account, second["id"], VERSION, POLICY, uuid4(),
    )
    job_worker = worker_principal(admin, ctx)
    job_worker = replace(
        job_worker,
        context=replace(
            job_worker.context, scopes=frozenset({"email.document.process"}),
        ),
    )
    fake_docker(
        monkeypatch, processor=processor,
        output=process_request(encode_request(raw, "1.2", second["sha256"])),
    )
    completed = jobs.run_once(job_worker, account, processor)
    assert completed is not None and completed["status"] == "completed"
    assert completed["extraction_id"] is not None
    core = DataCoreStore(store)
    bridge_ctx = pg.datacore_context(ctx)
    core.bridge_current_email_version(
        bridge_ctx, second["evidence_id"], uuid4(),
        code_revision="email-pdf-tier-test-v1",
    )
    core.bridge_email_attachment(
        bridge_ctx, second["id"], uuid4(),
        code_revision="email-pdf-tier-test-v1",
    )
    derived = core.bridge_email_document_extraction(
        bridge_ctx, completed["extraction_id"], uuid4(),
        code_revision="email-pdf-tier-test-v1",
    )
    reviewer = replace(
        ctx, scopes=ctx.scopes | frozenset({"knowledge.review", "brain.content.read"}),
    )
    with store.transaction(reviewer) as conn:
        row = conn.execute(
            "SELECT d.evidence_id,d.body_sha256,e.source_version_id,e.sha256 "
            "FROM brain_normalized_documents d JOIN brain_evidence e "
            "ON e.tenant_id=d.tenant_id AND e.id=d.evidence_id WHERE d.id=%s",
            (derived.document_id,),
        ).fetchone()
    assert row is not None
    second_review = SourceTierReviews(store).publish(
        reviewer, row["evidence_id"], SourceTierReviewWrite(
            evidence_id=row["evidence_id"], document_id=derived.document_id,
            document_sha256=row["body_sha256"],
            source_version_id=row["source_version_id"], source_sha256=row["sha256"],
            source_tier="T3", authority_kind="internal_record",
            source_quote="pdfonlyproof",
        ), uuid4(),
    )["object_id"]
    replay = SourceTierEmailPdfReplayStore(store, processor)
    for review_id in (first_review, second_review):
        fake_docker(
            monkeypatch, processor=processor,
            output=process_request(encode_request(raw, "1.2", second["sha256"])),
        )
        replay.record_current_pdf_replay(
            _worker(ctx), review_id, expected_account_id=account,
        )
    with store.transaction(_worker(ctx)) as conn:
        rows = conn.execute(
            "SELECT review_id,evidence_id,parent_version_id,legacy_attachment_id,"
            "part_sha256,raw_sha256 FROM knowledge_source_tier_email_pdf_replays "
            "WHERE review_id IN (%s,%s) ORDER BY review_id",
            (first_review, second_review),
        ).fetchall()
    assert len(rows) == 2
    assert {row["review_id"] for row in rows} == {first_review, second_review}
    assert len({row["evidence_id"] for row in rows}) == 2
    assert len({row["parent_version_id"] for row in rows}) == 2
    assert {row["legacy_attachment_id"] for row in rows} == {
        first_receipt, second["id"],
    }
    assert len({row["part_sha256"] for row in rows}) == 1
    assert len({row["raw_sha256"] for row in rows}) == 1


def test_controlled_disconnect_winning_account_lock_refuses_receipt(
    database, tenant, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, admin, ctx, account, _, processor, review_id, _ = _prepared(
        database, tenant, monkeypatch,
    )
    proof_done = Event()
    original = replay_module.prove_email_attachment_pdf_derivation

    def observed_proof(*args, **kwargs):
        proof = original(*args, **kwargs)
        proof_done.set()
        return proof

    monkeypatch.setattr(replay_module, "prove_email_attachment_pdf_derivation", observed_proof)
    replay = SourceTierEmailPdfReplayStore(store, processor)
    with psycopg.connect(admin) as transition, ThreadPoolExecutor(max_workers=1) as pool:
        transition.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (f"{ctx.tenant_id}:{account}",),
        )
        future = pool.submit(
            replay.record_current_pdf_replay, _worker(ctx), review_id,
            expected_account_id=account,
        )
        try:
            assert proof_done.wait(timeout=5)
            # The replay must wait on the same transaction-scoped lock,
            # not merely happen to be slower than the admin update.
            deadline = time.monotonic() + 2
            waiting = 0
            while time.monotonic() < deadline:
                transition.execute("SELECT pg_stat_clear_snapshot()")
                waiting = transition.execute(
                    "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() "
                    "AND wait_event_type='Lock' AND wait_event='advisory'",
                ).fetchone()[0]
                if waiting:
                    break
                time.sleep(0.02)
            assert waiting and not future.done()
            transition.execute(
                "UPDATE mail_accounts SET status='disconnected' WHERE id=%s", (account,),
            )
        finally:
            transition.commit()
        with pytest.raises(Conflict):
            future.result(timeout=5)
    with store.transaction(_worker(ctx)) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_source_tier_email_pdf_replays "
            "WHERE review_id=%s", (review_id,),
        ).fetchone()["n"] == 0


def test_replay_winning_account_lock_finishes_before_controlled_disconnect(
    database, tenant, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, admin, ctx, account, _, processor, review_id, _ = _prepared(
        database, tenant, monkeypatch,
    )
    inside_final = Event()
    release = Event()

    def authorize() -> None:
        inside_final.set()
        assert release.wait(timeout=5)

    def disconnect() -> None:
        with psycopg.connect(admin) as conn:
            # Deliberately omit the cooperative advisory lock: even a direct
            # privileged status update must wait on the account row fence.
            conn.execute(
                "UPDATE mail_accounts SET status='disconnected' WHERE id=%s", (account,),
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        replay_future = pool.submit(
            SourceTierEmailPdfReplayStore(store, processor).record_current_pdf_replay,
            _worker(ctx), review_id, expected_account_id=account, authorize=authorize,
        )
        try:
            assert inside_final.wait(timeout=5), (
                replay_future.exception() if replay_future.done() else "worker still running"
            )
            disconnect_future = pool.submit(disconnect)
            with psycopg.connect(admin, autocommit=True) as observer:
                deadline = time.monotonic() + 2
                waiting = 0
                while time.monotonic() < deadline:
                    waiting = observer.execute(
                        "SELECT count(*) FROM pg_stat_activity "
                        "WHERE datname=current_database() AND wait_event_type='Lock' "
                    ).fetchone()[0]
                    if waiting:
                        break
                    time.sleep(0.02)
            assert waiting and not disconnect_future.done()
        finally:
            release.set()
        result = replay_future.result(timeout=5)
        disconnect_future.result(timeout=5)
    assert result["worker_observed_pdf_text_replay"] is True
    with store.transaction(_worker(ctx)) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_source_tier_email_pdf_replays "
            "WHERE review_id=%s", (review_id,),
        ).fetchone()["n"] == 1
        assert conn.execute(
            "SELECT status FROM mail_accounts WHERE id=%s", (account,),
        ).fetchone()["status"] == "disconnected"


def test_account_lock_function_is_granted_only_to_bound_tenant_login(
    database, tenant, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _, ctx, account, _, _, _, _ = _prepared(database, tenant, monkeypatch)
    with store.transaction(_worker(ctx)) as conn:
        assert conn.execute(
            "SELECT public.lock_email_pdf_replay_account(%s,%s) AS active",
            (ctx.tenant_id, account),
        ).fetchone()["active"] is True
        assert conn.execute(
            "SELECT public.lock_email_pdf_replay_account(%s,%s) AS active",
            (uuid4(), account),
        ).fetchone()["active"] is False
        assert conn.execute(
            "SELECT public.lock_email_pdf_replay_account(%s,%s) AS active",
            (ctx.tenant_id, uuid4()),
        ).fetchone()["active"] is False
    with database[0].transaction(_worker(ctx)) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.transaction():
                conn.execute(
                    "SELECT public.lock_email_pdf_replay_account(%s,%s)",
                    (ctx.tenant_id, account),
                )
