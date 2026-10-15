"""Fictional retained-MIME source-tier replay, including encrypted storage."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
import test_postgres as pg

from email_brain.blobs import EncryptedBlobStore
from email_brain.schemas import SearchRequest
from email_brain.store import AccessDenied, Conflict, IngestItem, NotFound, Store
from masterbrain.datacore.persistence import DataCoreStore
from masterbrain.knowledge_schema import SourceTierReviewWrite
from masterbrain.source_tier_email_replay import SourceTierEmailReplayStore
from masterbrain.source_tier_reviews import SourceTierReviews

pytestmark = pytest.mark.postgres
database, tenant = pg.database, pg.tenant


def _fixture(
    store: Store, ctx: pg.TenantContext, account: pg.UUID, *, key: str,
) -> tuple[str, str, bytes]:
    message: IngestItem = pg.item(key=key, body="Fictional Email tier proof")
    assert message.raw is not None
    store.ingest_page(ctx, account, None, key + "-page", [message])
    legacy = store.search(ctx, SearchRequest(query="Fictional Email tier proof"))[0]["evidence_id"]
    bridged = DataCoreStore(store).bridge_current_email_version(
        pg.datacore_context(ctx), legacy, uuid4(), code_revision="tier-email-fixture-v1",
    )
    reviewer = replace(
        ctx, scopes=ctx.scopes | frozenset({"knowledge.review", "brain.content.read"}),
    )
    with store.transaction(reviewer) as conn:
        row = conn.execute(
            "SELECT d.body_sha256,e.source_version_id,e.sha256 "
            "FROM brain_normalized_documents d JOIN brain_evidence e "
            "ON e.tenant_id=d.tenant_id AND e.id=d.evidence_id WHERE d.id=%s",
            (bridged.document_id,),
        ).fetchone()
    body = SourceTierReviewWrite(
        evidence_id=bridged.evidence_id, document_id=bridged.document_id,
        document_sha256=row["body_sha256"], source_version_id=row["source_version_id"],
        source_sha256=row["sha256"], source_tier="T3", authority_kind="internal_record",
        source_quote="Fictional Email tier proof",
    )
    review_id = SourceTierReviews(store).publish(
        reviewer, bridged.evidence_id, body, uuid4(),
    )["object_id"]
    return review_id, bridged.version_id, message.raw


def _worker(ctx: pg.TenantContext) -> pg.TenantContext:
    return replace(
        ctx, scopes=frozenset({"brain.document.publish", "email.evidence.read"}),
    )


@pytest.mark.parametrize("encrypted", [False, True], ids=["inline", "encrypted"])
def test_current_email_bytes_reproduce_reviewed_text(
    database, tenant, tmp_path: Path, encrypted: bool,
) -> None:
    base, _admin = database
    ctx, account = tenant
    store = base
    if encrypted:
        blobs = EncryptedBlobStore(
            tmp_path / "fictional-ciphertext",
            {(ctx.tenant_id, "test-key"): bytes(range(32))},
            {ctx.tenant_id: "test-key"},
        )
        store = Store(base.dsn, blobs=blobs)
    review_id, version_id, raw = _fixture(store, ctx, account, key="email-tier-fixture")
    replay = SourceTierEmailReplayStore(store)
    result = replay.record_current_text_replay(_worker(ctx), review_id)
    assert result == replay.record_current_text_replay(_worker(ctx), review_id)
    assert result == {
        "review_id": review_id, "worker_observed_text_replay": True,
        "source_effects": False, "financial_claim_approved": False,
    }
    with store.transaction(_worker(ctx)) as conn:
        receipt = conn.execute(
            "SELECT source_sha256,source_size_bytes,text_sha256,normalizer,parser_version "
            "FROM knowledge_source_tier_email_replays WHERE review_id=%s", (review_id,),
        ).fetchone()
        assert receipt["source_sha256"] == hashlib.sha256(raw).hexdigest()
        assert receipt["source_size_bytes"] == len(raw)
        assert receipt["text_sha256"] != receipt["source_sha256"]
        assert receipt["normalizer"] == "email-message-v1"
        assert receipt["parser_version"] == "stdlib-mime-v5"
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_claims",
        ).fetchone()["n"] == 0
        assert conn.execute(
            "SELECT size_bytes FROM brain_source_versions WHERE id=%s", (version_id,),
        ).fetchone()["size_bytes"] == len(raw)
    if encrypted:
        assert raw not in next((tmp_path / "fictional-ciphertext").rglob("*.blob")).read_bytes()


def test_email_replay_requires_scopes_current_version_and_grant(database, tenant) -> None:
    store, _admin = database
    ctx, account = tenant
    review_id, _version_id, _raw = _fixture(store, ctx, account, key="email-tier-stale")
    replay = SourceTierEmailReplayStore(store)
    with pytest.raises(AccessDenied):
        replay.record_current_text_replay(ctx, review_id)
    with pytest.raises(NotFound):
        replay.record_current_text_replay(
            replace(_worker(ctx), source_ids=frozenset()), review_id,
        )
    newer = pg.item(key="email-tier-new", body="A newer fictional message")
    store.ingest_page(ctx, account, "email-tier-stale-page", "email-tier-new-page", [newer])
    with pytest.raises(Conflict, match="basis changed"):
        replay.record_current_text_replay(_worker(ctx), review_id)
    with store.transaction(_worker(ctx)) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_source_tier_email_replays "
            "WHERE review_id=%s", (review_id,),
        ).fetchone()["n"] == 0


def test_email_replay_revocation_and_protected_table(database, tenant) -> None:
    store, admin = database
    ctx, account = tenant
    review_id, _version_id, _raw = _fixture(store, ctx, account, key="email-tier-revoke")
    replay = SourceTierEmailReplayStore(store)

    def revoked() -> None:
        raise AccessDenied("worker revoked")

    with pytest.raises(AccessDenied, match="worker revoked"):
        replay.record_current_text_replay(_worker(ctx), review_id, authorize=revoked)
    with store.transaction(_worker(ctx)) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_source_tier_email_replays "
            "WHERE review_id=%s", (review_id,),
        ).fetchone()["n"] == 0
    replay.record_current_text_replay(_worker(ctx), review_id)
    with psycopg.connect(admin) as conn:
        with pytest.raises(psycopg.errors.RaiseException):
            with conn.transaction():
                conn.execute("TRUNCATE knowledge_source_tier_email_replays")


def test_encrypted_ciphertext_tampering_leaves_no_replay_receipt(
    database, tenant, tmp_path: Path,
) -> None:
    base, _admin = database
    ctx, account = tenant
    root = tmp_path / "fictional-ciphertext"
    blobs = EncryptedBlobStore(
        root, {(ctx.tenant_id, "test-key"): bytes(range(32))},
        {ctx.tenant_id: "test-key"},
    )
    store = Store(base.dsn, blobs=blobs)
    review_id, _version_id, _raw = _fixture(store, ctx, account, key="email-tier-tamper")
    ciphertext = next(root.rglob("*.blob"))
    original = ciphertext.read_bytes()
    ciphertext.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
    with pytest.raises(Conflict, match="retained bytes unavailable or changed"):
        SourceTierEmailReplayStore(store).record_current_text_replay(_worker(ctx), review_id)
    with store.transaction(_worker(ctx)) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_source_tier_email_replays "
            "WHERE review_id=%s", (review_id,),
        ).fetchone()["n"] == 0


def test_email_version_race_after_byte_read_rolls_back(
    database, tenant, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _admin = database
    ctx, account = tenant
    review_id, _version_id, _raw = _fixture(store, ctx, account, key="email-tier-race")
    original = store.load_raw

    def changed(*args: object, **kwargs: object) -> bytes:
        raw = original(*args, **kwargs)  # type: ignore[arg-type]
        store.ingest_page(
            ctx, account, "email-tier-race-page", "email-tier-race-new-page",
            [pg.item(key="email-tier-race-new", body="Updated fictional version")],
        )
        return raw

    monkeypatch.setattr(store, "load_raw", changed)
    with pytest.raises(Conflict, match="basis changed"):
        SourceTierEmailReplayStore(store).record_current_text_replay(_worker(ctx), review_id)
    with store.transaction(_worker(ctx)) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_source_tier_email_replays "
            "WHERE review_id=%s", (review_id,),
        ).fetchone()["n"] == 0
