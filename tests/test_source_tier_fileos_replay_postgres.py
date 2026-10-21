"""Fictional PostgreSQL proof of reviewed FileOS text-byte replay."""

from __future__ import annotations

import hashlib
import json
import secrets
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
import test_postgres as pg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from test_statement_fileos_replay_postgres import source_file_document
from test_statement_persistence_postgres import TEXT, worker

import masterbrain.datacore.current_fileos_text_replay as replay_core
from email_brain.migrate import grant_tenant_runtime
from email_brain.store import AccessDenied, Conflict, NotFound, Store
from masterbrain.knowledge_schema import SourceTierReviewWrite
from masterbrain.source_tier_fileos_controller import (
    FileOSTierReplayControllerError,
    run_source_tier_fileos_controller,
)
from masterbrain.source_tier_fileos_replay import SourceTierFileOSReplayStore
from masterbrain.source_tier_reviews import SourceTierReviews

pytestmark = pytest.mark.postgres
database, tenant = pg.database, pg.tenant
QUOTE = "Account No: 000000"


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


def test_exact_reviewed_text_replay_is_point_in_time_not_financial_approval(
    database, tenant, tmp_path: Path,
):
    store, admin = database
    root = tmp_path / "fictional-files"
    raw = b"\xef\xbb\xbf" + TEXT.replace("\n", "\r\n").encode() + b"  \n"
    document_id, _, _, _ = source_file_document(admin, tenant[0], root, raw=raw)
    review_id = _review(store, tenant[0], document_id)
    replay = SourceTierFileOSReplayStore(store)
    result = replay.record_current_text_replay(worker(tenant[0]), review_id, root)
    assert result == replay.record_current_text_replay(worker(tenant[0]), review_id, root)
    assert result == {
        "review_id": review_id, "worker_observed_text_replay": True,
        "source_effects": False, "financial_claim_approved": False,
    }
    with store.transaction(worker(tenant[0])) as conn:
        saved = conn.execute(
            "SELECT source_sha256,text_sha256,source_size_bytes,normalizer "
            "FROM knowledge_source_tier_fileos_replays WHERE review_id=%s",
            (review_id,),
        ).fetchone()
        assert saved is not None
        assert saved["source_sha256"] == hashlib.sha256(raw).hexdigest()
        assert saved["text_sha256"] == hashlib.sha256(TEXT.encode()).hexdigest()
        assert saved["source_sha256"] != saved["text_sha256"]
        assert saved["source_size_bytes"] == len(raw)
        assert saved["normalizer"] == "fileos-text-v1"
        assert conn.execute("SELECT count(*) AS n FROM knowledge_claims").fetchone()["n"] == 0


def test_wrong_root_changed_bytes_grants_and_stale_version_fail_closed(
    database, tenant, tmp_path: Path,
):
    store, admin = database
    root = tmp_path / "fictional-files"
    document_id, item_id, version_id, _ = source_file_document(admin, tenant[0], root)
    review_id = _review(store, tenant[0], document_id)
    replay = SourceTierFileOSReplayStore(store)
    with pytest.raises(AccessDenied):
        replay.record_current_text_replay(tenant[0], review_id, root)
    with pytest.raises(NotFound):
        replay.record_current_text_replay(
            replace(worker(tenant[0]), source_ids=frozenset()), review_id, root,
        )
    other = tmp_path / "wrong-root"
    other.mkdir()
    (other / "fictional-statement.txt").write_text(TEXT)
    with pytest.raises(Conflict, match="basis changed"):
        replay.record_current_text_replay(worker(tenant[0]), review_id, other)
    (root / "fictional-statement.txt").write_text("changed")
    with pytest.raises(Conflict, match="text replay failed"):
        replay.record_current_text_replay(worker(tenant[0]), review_id, root)
    (root / "fictional-statement.txt").write_text(TEXT)
    with psycopg.connect(admin) as conn:
        next_version = "version_" + uuid4().hex
        conn.execute(
            "INSERT INTO brain_source_versions(tenant_id,source_id,item_id,id,"
            "observed_at,sha256,size_bytes,media_type,metadata) "
            "SELECT tenant_id,source_id,item_id,%s,observed_at,sha256,size_bytes,"
            "media_type,metadata FROM brain_source_versions WHERE tenant_id=%s AND id=%s",
            (next_version, tenant[0].tenant_id, version_id),
        )
        conn.execute(
            "UPDATE brain_source_items SET current_version_id=%s "
            "WHERE tenant_id=%s AND id=%s",
            (next_version, tenant[0].tenant_id, item_id),
        )
    with pytest.raises(Conflict, match="basis changed"):
        replay.record_current_text_replay(worker(tenant[0]), review_id, root)
    with store.transaction(worker(tenant[0])) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_source_tier_fileos_replays "
            "WHERE review_id=%s", (review_id,),
        ).fetchone()["n"] == 0


def test_concurrent_replay_and_direct_sql_guard(database, tenant, tmp_path: Path):
    store, admin = database
    root = tmp_path / "fictional-files"
    document_id, _, _, _ = source_file_document(admin, tenant[0], root)
    review_id = _review(store, tenant[0], document_id)
    replay = SourceTierFileOSReplayStore(store)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(
            lambda _: replay.record_current_text_replay(worker(tenant[0]), review_id, root),
            range(6),
        ))
    assert all(result["review_id"] == review_id for result in results)
    with store.transaction(worker(tenant[0])) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_source_tier_fileos_replays "
            "WHERE review_id=%s", (review_id,),
        ).fetchone()["n"] == 1
    with psycopg.connect(admin) as conn:
        with pytest.raises(psycopg.errors.RaiseException):
            with conn.transaction():
                conn.execute("TRUNCATE knowledge_source_tier_fileos_replays")
        with pytest.raises(psycopg.errors.RaiseException, match="invalid source tier FileOS"):
            with conn.transaction():
                conn.execute(
                    "INSERT INTO knowledge_source_tier_fileos_replays(tenant_id,review_id,"
                    "evidence_id,document_id,source_version_id,source_id,actor_id,"
                    "source_sha256,source_size_bytes,text_sha256,normalizer,"
                    "root_binding_sha256) SELECT tenant_id,%s,evidence_id,document_id,"
                    "source_version_id,source_id,actor_id,%s,source_size_bytes,"
                    "text_sha256,normalizer,root_binding_sha256 "
                    "FROM knowledge_source_tier_fileos_replays WHERE review_id=%s",
                    ("stier_" + "f" * 32, "0" * 64, review_id),
                )


def test_symlink_and_between_transaction_version_race_fail_closed(
    database, tenant, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    store, admin = database
    root = tmp_path / "fictional-files"
    document_id, item_id, version_id, _ = source_file_document(admin, tenant[0], root)
    review_id = _review(store, tenant[0], document_id)
    replay = SourceTierFileOSReplayStore(store)
    leaf = root / "fictional-statement.txt"
    leaf.unlink()
    outside = tmp_path / "outside.txt"
    outside.write_text(TEXT)
    leaf.symlink_to(outside)
    with pytest.raises(Conflict, match="source unavailable or changed"):
        replay.record_current_text_replay(worker(tenant[0]), review_id, root)
    leaf.unlink()
    leaf.write_text(TEXT)

    original = replay_core.read_confined_file

    def race(*args: object, **kwargs: object):
        opened = original(*args, **kwargs)  # type: ignore[arg-type]
        next_version = "version_" + uuid4().hex
        with psycopg.connect(admin) as conn:
            conn.execute(
                "INSERT INTO brain_source_versions(tenant_id,source_id,item_id,id,"
                "observed_at,sha256,size_bytes,media_type,metadata) "
                "SELECT tenant_id,source_id,item_id,%s,observed_at,sha256,size_bytes,"
                "media_type,metadata FROM brain_source_versions "
                "WHERE tenant_id=%s AND id=%s",
                (next_version, tenant[0].tenant_id, version_id),
            )
            conn.execute(
                "UPDATE brain_source_items SET current_version_id=%s "
                "WHERE tenant_id=%s AND id=%s",
                (next_version, tenant[0].tenant_id, item_id),
            )
        return opened

    monkeypatch.setattr(replay_core, "read_confined_file", race)
    with pytest.raises(Conflict, match="basis changed"):
        replay.record_current_text_replay(worker(tenant[0]), review_id, root)
    with store.transaction(worker(tenant[0])) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_source_tier_fileos_replays "
            "WHERE review_id=%s", (review_id,),
        ).fetchone()["n"] == 0


def test_authenticated_command_checks_then_replays_only_selected_review(
    database, tenant, tmp_path: Path,
):
    store, admin = database
    root = tmp_path / "fictional-files"
    document_id, _, _, source_id = source_file_document(admin, tenant[0], root)
    review_id = _review(store, tenant[0], document_id)
    state = tmp_path / "private-state"
    state.mkdir(mode=0o700)
    token = secrets.token_urlsafe(40)
    token_path = state / "token"
    token_path.write_text(token)
    token_path.chmod(0o600)
    credentials = [{
        "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
        "tenant_id": str(tenant[0].tenant_id), "actor_id": str(tenant[0].actor_id),
        "scopes": ["brain.document.publish"], "client_kind": "worker",
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    }]
    credentials_path = state / "credentials.json"
    credentials_path.write_text(json.dumps(credentials))
    credentials_path.chmod(0o600)
    config_path = state / "tier-replay.json"
    config = {
        "version": 1, "source_id": source_id, "root": str(root),
        "credentials_file": str(credentials_path), "token_file": str(token_path),
    }
    config_path.write_text(json.dumps(config))
    config_path.chmod(0o600)

    role = "test_tier_replay_" + uuid4().hex[:12]
    password = secrets.token_urlsafe(32)
    with psycopg.connect(admin) as conn:
        conn.execute(
            sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD {}").format(
                sql.Identifier(role), sql.Literal(password),
            )
        )
        grant_tenant_runtime(conn, role, tenant[0].tenant_id)
    bound_dsn = make_conninfo(admin, user=role, password=password)

    before_bytes = (root / "fictional-statement.txt").read_bytes()
    for refused in (store.dsn, admin):
        with pytest.raises(FileOSTierReplayControllerError):
            run_source_tier_fileos_controller(
                config_path, refused, review_id, check=True, tenant_bound_db=True,
            )
    check = run_source_tier_fileos_controller(
        config_path, bound_dsn, review_id, check=True, tenant_bound_db=True,
    )
    assert check["execution_verified"] is False
    with store.transaction(worker(tenant[0])) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_source_tier_fileos_replays "
            "WHERE review_id=%s", (review_id,),
        ).fetchone()["n"] == 0
    executed = run_source_tier_fileos_controller(
        config_path, bound_dsn, review_id, tenant_bound_db=True,
    )
    assert executed["worker_observed_text_replay"] is True
    assert executed["financial_claim_approved"] is False
    assert (root / "fictional-statement.txt").read_bytes() == before_bytes
    config_path.write_text(json.dumps({**config, "source_id": "wrong_source"}))
    config_path.chmod(0o600)
    with pytest.raises(FileOSTierReplayControllerError, match="sensitive details suppressed"):
        run_source_tier_fileos_controller(
            config_path, bound_dsn, review_id, tenant_bound_db=True,
        )


def test_worker_revocation_before_receipt_rolls_back(
    database, tenant, tmp_path: Path,
):
    store, admin = database
    root = tmp_path / "fictional-files"
    document_id, _, _, source_id = source_file_document(admin, tenant[0], root)
    review_id = _review(store, tenant[0], document_id)
    replay = SourceTierFileOSReplayStore(store)

    def revoked() -> None:
        raise AccessDenied("worker token revoked")

    with pytest.raises(NotFound):
        replay.record_current_text_replay(
            worker(tenant[0]), review_id, root, expected_source_id="wrong_source",
        )
    with pytest.raises(AccessDenied):
        replay.record_current_text_replay(
            worker(tenant[0]), review_id, root,
            expected_source_id=source_id, authorize=revoked,
        )
    with store.transaction(worker(tenant[0])) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_source_tier_fileos_replays "
            "WHERE review_id=%s", (review_id,),
        ).fetchone()["n"] == 0
