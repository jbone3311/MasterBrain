"""Fictional database and restricted-pipe proof of PDF source-tier replay."""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
import test_postgres as pg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from test_sandbox_runner import IMAGE, fake_docker
from test_statement_persistence_postgres import worker

import masterbrain.datacore.current_fileos_pdf_replay as replay_core
import masterbrain.source_tier_fileos_pdf_controller as control
from email_brain.migrate import grant_tenant_runtime
from email_brain.store import AccessDenied, Conflict, NotFound, Store
from email_brain.synthetic_formats import pdf_bytes
from masterbrain.datacore.contracts import stable_id
from masterbrain.datacore.document_contract import PDF_TYPE, encode_request
from masterbrain.datacore.document_processor import DockerDocumentProcessor
from masterbrain.datacore.document_worker import process_request
from masterbrain.datacore.fileos import fileos_root_binding_sha256
from masterbrain.knowledge_schema import SourceTierReviewWrite
from masterbrain.source_tier_fileos_pdf_replay import SourceTierFileOSPdfReplayStore
from masterbrain.source_tier_reviews import SourceTierReviews

pytestmark = pytest.mark.postgres
database, tenant = pg.database, pg.tenant
QUOTE = "Fictional issuer statement"


def _review(store: Store, ctx: pg.TenantContext, document_id: str) -> str:
    reviewer = replace(
        ctx, scopes=ctx.scopes | frozenset({"knowledge.review", "brain.content.read"}),
    )
    with store.transaction(reviewer) as conn:
        row = conn.execute(
            "SELECT d.evidence_id,d.body_sha256,e.source_version_id,e.sha256 "
            "FROM brain_normalized_documents d JOIN brain_evidence e "
            "ON e.tenant_id=d.tenant_id AND e.id=d.evidence_id WHERE d.id=%s",
            (document_id,),
        ).fetchone()
    assert row is not None
    body = SourceTierReviewWrite(
        evidence_id=row["evidence_id"], document_id=document_id,
        document_sha256=row["body_sha256"],
        source_version_id=row["source_version_id"],
        source_sha256=row["sha256"], source_tier="T3",
        authority_kind="internal_record", source_quote=QUOTE,
    )
    return SourceTierReviews(store).publish(
        reviewer, row["evidence_id"], body, uuid4(),
    )["object_id"]


def _prepared(
    database, tenant, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    raw: bytes | None = None,
):
    store, admin = database
    ctx = tenant[0]
    root = tmp_path / "fictional-pdf"
    raw = pdf_bytes((QUOTE, "Amount 125 USD")) if raw is None else raw
    digest = hashlib.sha256(raw).hexdigest()
    source_id = stable_id("source", str(uuid4()))
    item_id = stable_id("item", source_id)
    version_id = stable_id("version", item_id)
    request = encode_request(raw, version_id, "statement.pdf", digest, PDF_TYPE)
    output = process_request(request)
    from masterbrain.datacore.document_contract import decode_result, source_for
    result = decode_result(output, source_for(raw, version_id, "statement.pdf", digest, PDF_TYPE))
    processor, _, _ = fake_docker(
        monkeypatch, processor=DockerDocumentProcessor(IMAGE), output=output,
    )
    # The database fixture deliberately uses the same stable version ID.
    root.mkdir()
    (root / "statement.pdf").write_bytes(raw)
    now = datetime(2026, 10, 15, tzinfo=UTC)
    evidence_id = stable_id("evidence", version_id)
    document_id = stable_id("document", evidence_id, result.text)
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO brain_sources(tenant_id,id,kind,display_name,root_binding_sha256) "
            "VALUES (%s,%s,'fileos','Fictional PDF replay',%s)",
            (ctx.tenant_id, source_id, fileos_root_binding_sha256(root)),
        )
        conn.execute(
            "INSERT INTO brain_source_items(tenant_id,source_id,id,locator,first_seen_at,"
            "last_seen_at) VALUES (%s,%s,%s,'statement.pdf',%s,%s)",
            (ctx.tenant_id, source_id, item_id, now, now),
        )
        conn.execute(
            "INSERT INTO brain_source_versions(tenant_id,source_id,item_id,id,observed_at,"
            "sha256,size_bytes,media_type,metadata) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'{}'::jsonb)",
            (ctx.tenant_id, source_id, item_id, version_id, now, digest,
             len(raw), PDF_TYPE),
        )
        conn.execute(
            "UPDATE brain_source_items SET current_version_id=%s "
            "WHERE tenant_id=%s AND id=%s", (version_id, ctx.tenant_id, item_id),
        )
        conn.execute(
            "INSERT INTO brain_evidence(tenant_id,id,source_version_id,sha256,storage,"
            "retained) VALUES (%s,%s,%s,%s,'source_bound',false)",
            (ctx.tenant_id, evidence_id, version_id, digest),
        )
        conn.execute(
            "INSERT INTO brain_normalized_documents(tenant_id,id,evidence_id,normalizer,"
            "body_sha256,body) VALUES (%s,%s,%s,%s,%s,%s)",
            (ctx.tenant_id, document_id, evidence_id, processor.processor_version,
             hashlib.sha256(result.text.encode()).hexdigest(), result.text),
        )
    return store, admin, ctx, root, processor, document_id, item_id, version_id, result


def test_exact_reviewed_pdf_replay_is_immutable_and_not_financial(
    database, tenant, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, admin, ctx, root, processor, document_id, _, _, result = _prepared(
        database, tenant, tmp_path, monkeypatch,
    )
    assert result.status == "extracted" and QUOTE in result.text
    review_id = _review(store, ctx, document_id)
    raw = (root / "statement.pdf").read_bytes()
    replay = SourceTierFileOSPdfReplayStore(store, processor)
    first = replay.record_current_pdf_replay(worker(ctx), review_id, root)
    # The simulated container is one-shot; a second replay gets a fresh
    # synthetic container with the same pinned image and exact output.
    request = encode_request(
        raw, result.source.version_id, "statement.pdf",
        hashlib.sha256(raw).hexdigest(), PDF_TYPE,
    )
    fake_docker(monkeypatch, processor=processor, output=process_request(request))
    assert first == replay.record_current_pdf_replay(worker(ctx), review_id, root)
    assert first == {
        "review_id": review_id, "worker_observed_pdf_text_replay": True,
        "source_effects": False, "financial_claim_approved": False,
    }
    with store.transaction(worker(ctx)) as conn:
        saved = conn.execute(
            "SELECT source_sha256,source_size_bytes,text_sha256,normalizer,page_count "
            "FROM knowledge_source_tier_fileos_pdf_replays WHERE review_id=%s",
            (review_id,),
        ).fetchone()
        assert saved is not None
        assert saved["source_sha256"] == hashlib.sha256(raw).hexdigest()
        assert saved["source_size_bytes"] == len(raw)
        assert saved["text_sha256"] == hashlib.sha256(result.text.encode()).hexdigest()
        assert saved["normalizer"] == processor.processor_version
        assert saved["page_count"] == 1
        assert conn.execute("SELECT count(*) AS n FROM knowledge_claims").fetchone()["n"] == 0
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.transaction():
                conn.execute(
                    "UPDATE knowledge_source_tier_fileos_pdf_replays "
                    "SET page_count=2 WHERE review_id=%s", (review_id,),
                )
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.transaction():
                conn.execute(
                    "DELETE FROM knowledge_source_tier_fileos_pdf_replays "
                    "WHERE review_id=%s", (review_id,),
                )
        with pytest.raises(psycopg.errors.RaiseException, match="invalid source tier FileOS PDF"):
            with conn.transaction():
                conn.execute(
                    "INSERT INTO knowledge_source_tier_fileos_pdf_replays(tenant_id,"
                    "review_id,evidence_id,document_id,source_version_id,source_id,"
                    "actor_id,source_sha256,source_size_bytes,text_sha256,normalizer,"
                    "page_count,root_binding_sha256) "
                    "SELECT tenant_id,%s,evidence_id,document_id,source_version_id,"
                    "source_id,actor_id,%s,source_size_bytes,text_sha256,normalizer,"
                    "page_count,root_binding_sha256 "
                    "FROM knowledge_source_tier_fileos_pdf_replays WHERE review_id=%s",
                    ("stier_" + "f" * 32, "0" * 64, review_id),
                )
    with psycopg.connect(admin) as conn:
        with pytest.raises(psycopg.errors.RaiseException):
            with conn.transaction():
                conn.execute(
                    "UPDATE knowledge_source_tier_fileos_pdf_replays "
                    "SET page_count=2 WHERE review_id=%s", (review_id,),
                )
        with pytest.raises(psycopg.errors.RaiseException):
            with conn.transaction():
                conn.execute(
                    "DELETE FROM knowledge_source_tier_fileos_pdf_replays "
                    "WHERE review_id=%s", (review_id,),
                )
    with pytest.raises(AccessDenied):
        with store.transaction(replace(worker(ctx), tenant_id=uuid4())) as conn:
            conn.execute("SELECT count(*) FROM knowledge_source_tier_fileos_pdf_replays")
    assert (root / "statement.pdf").read_bytes() == raw


def test_wrong_scope_source_changed_and_revocation_leave_no_receipt(
    database, tenant, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _, ctx, root, processor, document_id, _, _, _ = _prepared(
        database, tenant, tmp_path, monkeypatch,
    )
    review_id = _review(store, ctx, document_id)
    replay = SourceTierFileOSPdfReplayStore(store, processor)
    with pytest.raises(AccessDenied):
        replay.record_current_pdf_replay(ctx, review_id, root)
    with pytest.raises(NotFound):
        replay.record_current_pdf_replay(
            replace(worker(ctx), source_ids=frozenset()), review_id, root,
        )
    with pytest.raises(NotFound):
        replay.record_current_pdf_replay(
            worker(ctx), review_id, root, expected_source_id="wrong_source",
        )
    with pytest.raises(AccessDenied):
        replay.record_current_pdf_replay(
            worker(ctx), review_id, root,
            authorize=lambda: (_ for _ in ()).throw(AccessDenied("revoked")),
        )
    (root / "statement.pdf").write_bytes(pdf_bytes(("Changed statement",)))
    with pytest.raises(Conflict, match="unavailable or changed"):
        replay.record_current_pdf_replay(worker(ctx), review_id, root)
    with store.transaction(worker(ctx)) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_source_tier_fileos_pdf_replays "
            "WHERE review_id=%s", (review_id,),
        ).fetchone()["n"] == 0


def test_between_read_version_change_and_direct_sql_guard(
    database, tenant, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, admin, ctx, root, processor, document_id, item_id, version_id, _ = _prepared(
        database, tenant, tmp_path, monkeypatch,
    )
    review_id = _review(store, ctx, document_id)
    original = replay_core.read_confined_file

    def race(*args: object, **kwargs: object):
        opened = original(*args, **kwargs)  # type: ignore[arg-type]
        next_version = "version_" + uuid4().hex
        with psycopg.connect(admin) as conn:
            conn.execute(
                "INSERT INTO brain_source_versions(tenant_id,source_id,item_id,id,"
                "observed_at,sha256,size_bytes,media_type,metadata) "
                "SELECT tenant_id,source_id,item_id,%s,observed_at,sha256,"
                "size_bytes,media_type,metadata FROM brain_source_versions "
                "WHERE tenant_id=%s AND id=%s",
                (next_version, ctx.tenant_id, version_id),
            )
            conn.execute(
                "UPDATE brain_source_items SET current_version_id=%s "
                "WHERE tenant_id=%s AND id=%s",
                (next_version, ctx.tenant_id, item_id),
            )
        return opened

    monkeypatch.setattr(replay_core, "read_confined_file", race)
    replay = SourceTierFileOSPdfReplayStore(store, processor)
    with pytest.raises(Conflict, match="basis changed"):
        replay.record_current_pdf_replay(worker(ctx), review_id, root)
    with store.transaction(worker(ctx)) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_source_tier_fileos_pdf_replays "
            "WHERE review_id=%s", (review_id,),
        ).fetchone()["n"] == 0
    with psycopg.connect(admin) as conn:
        with pytest.raises(psycopg.errors.RaiseException):
            with conn.transaction():
                conn.execute("TRUNCATE knowledge_source_tier_fileos_pdf_replays")


def test_tenant_bound_command_checks_then_replays_only_selected_pdf(
    database, tenant, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, admin, ctx, root, processor, document_id, _, _, _ = _prepared(
        database, tenant, tmp_path, monkeypatch,
    )
    review_id = _review(store, ctx, document_id)
    state = tmp_path / "private-state"
    state.mkdir(mode=0o700)
    token = secrets.token_urlsafe(40)
    token_path = state / "token"
    token_path.write_text(token)
    token_path.chmod(0o600)
    credentials = [{
        "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
        "tenant_id": str(ctx.tenant_id), "actor_id": str(ctx.actor_id),
        "scopes": ["brain.document.publish"], "client_kind": "worker",
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    }]
    credentials_path = state / "credentials.json"
    credentials_path.write_text(json.dumps(credentials))
    credentials_path.chmod(0o600)
    config_path = state / "pdf-replay.json"
    config = {
        "version": 1, "source_id": "placeholder", "root": str(root),
        "document_image_id": IMAGE, "docker_binary": "/usr/bin/docker",
        "credentials_file": str(credentials_path), "token_file": str(token_path),
    }
    with store.transaction(worker(ctx)) as conn:
        source_id = conn.execute(
            "SELECT i.source_id FROM brain_normalized_documents d "
            "JOIN brain_evidence e ON e.tenant_id=d.tenant_id AND e.id=d.evidence_id "
            "JOIN brain_source_versions v ON v.tenant_id=e.tenant_id "
            "AND v.id=e.source_version_id "
            "JOIN brain_source_items i ON i.tenant_id=v.tenant_id AND i.id=v.item_id "
            "WHERE d.id=%s", (document_id,),
        ).fetchone()["source_id"]
    config["source_id"] = source_id
    config_path.write_text(json.dumps(config))
    config_path.chmod(0o600)
    role = "test_pdf_tier_" + uuid4().hex[:12]
    password = secrets.token_urlsafe(32)
    with psycopg.connect(admin) as conn:
        conn.execute(
            sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD {}").format(
                sql.Identifier(role), sql.Literal(password),
            )
        )
        grant_tenant_runtime(conn, role, ctx.tenant_id)
    bound_dsn = make_conninfo(admin, user=role, password=password)
    monkeypatch.setattr(control, "DockerDocumentProcessor", lambda *args, **kwargs: processor)
    before = (root / "statement.pdf").read_bytes()
    for refused in (store.dsn, admin):
        with pytest.raises(control.FileOSTierPdfControllerError):
            control.run_source_tier_fileos_pdf_controller(
                config_path, refused, review_id, check=True, tenant_bound_db=True,
            )
    check = control.run_source_tier_fileos_pdf_controller(
        config_path, bound_dsn, review_id, check=True, tenant_bound_db=True,
    )
    assert check["execution_verified"] is False
    with store.transaction(worker(ctx)) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_source_tier_fileos_pdf_replays "
            "WHERE review_id=%s", (review_id,),
        ).fetchone()["n"] == 0
    executed = control.run_source_tier_fileos_pdf_controller(
        config_path, bound_dsn, review_id, tenant_bound_db=True,
    )
    assert executed["worker_observed_pdf_text_replay"] is True
    assert executed["financial_claim_approved"] is False
    assert (root / "statement.pdf").read_bytes() == before
    config["source_id"] = "wrong_source"
    config_path.write_text(json.dumps(config))
    config_path.chmod(0o600)
    with pytest.raises(control.FileOSTierPdfControllerError):
        control.run_source_tier_fileos_pdf_controller(
            config_path, bound_dsn, review_id, tenant_bound_db=True,
        )


