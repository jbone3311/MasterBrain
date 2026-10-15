"""Synthetic PostgreSQL recovery, races, immutable history and API boundaries."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from email.message import EmailMessage
from threading import Barrier
from unittest.mock import MagicMock
from uuid import uuid4

import psycopg
import pytest
import test_postgres as pg
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import make_conninfo
from test_service import TOKEN, registry

from email_brain import store as persistence
from email_brain.api import create_app
from email_brain.auth import Principal
from email_brain.migrate import RUNTIME_INSERT, RUNTIME_SELECT, migrate
from email_brain.recovery import Recovery, RecoveryUnavailable
from email_brain.schemas import SearchRequest
from email_brain.store import AccessDenied, Conflict, NotFound, Store

database, tenant = pg.database, pg.tenant


def test_populated_rewrite_override_requires_explicit_boolean():
    from pathlib import Path

    with pytest.raises(ValueError, match="allow_populated_rewrite must be boolean"):
        migrate("not-used", Path("migrations"), allow_populated_rewrite="yes")  # type: ignore[arg-type]


def held(store, ctx, account, monkeypatch, *, raw=None, cursor=None, key="held"):
    message = replace(
        pg.item(key),
        raw=pg.item().raw if raw is None else raw,
        thread_id="thread-1",
        mailbox_ids=("inbox",),
        keywords=("$seen",),
    )
    with monkeypatch.context() as patch:
        patch.setattr(persistence, "prepare_mime", lambda raw: (None, [], True))
        store.ingest_page(ctx, account, cursor, key, [message])
    return store.quarantines(ctx, account)["results"][0]["id"]


def retry(store, ctx, account, receipt):
    return Recovery(store).retry(
        Principal(ctx, "human"), account, receipt, persistence.PARSER_VERSION
    )


def test_library_requires_human_and_both_scopes_before_sql():
    store = MagicMock(spec=Store)
    # Real scope guard, not a permissive mock.
    store.require = Store.require
    ctx = pg.TenantContext(uuid4(), uuid4(), frozenset({"email.review"}), uuid4())
    for kind, scopes in (
        ("assistant", {"email.review", "email.evidence.read"}),
        ("human", {"email.review"}),
        ("human", {"email.evidence.read"}),
    ):
        with pytest.raises(AccessDenied):
            Recovery(store).retry(
                Principal(replace(ctx, scopes=frozenset(scopes)), kind),
                uuid4(),
                uuid4(),
                persistence.PARSER_VERSION,
            )
    store.transaction.assert_not_called()


def test_api_denies_missing_scope_and_rejects_untrusted_parameters(monkeypatch):
    store = MagicMock(spec=Store)
    path = f"/v1/accounts/{uuid4()}/quarantine/{uuid4()}/retry"
    headers = {"Authorization": f"Bearer {TOKEN}"}
    body = {"expected_parser_version": persistence.PARSER_VERSION}
    client = TestClient(create_app(store, registry({"email.review", "email.evidence.read"})))
    assert client.post(path, json=body).status_code == 401
    assert client.post(path, json={**body, "raw": "private"}, headers=headers).status_code == 422
    assert client.post(path, json={}, headers=headers).status_code == 422
    for scopes, kind in (({"email.evidence.read"}, "assistant"), ({"email.review"}, "human")):
        if kind == "assistant":
            authenticator = MagicMock()
            authenticator.authenticate.return_value = Principal(
                registry(scopes).authenticate(TOKEN).context, "assistant"
            )
        else:
            authenticator = registry(scopes, kind)
        denied = TestClient(create_app(store, authenticator))
        # Mock must not bypass the library's scope guard.
        store.require = Store.require
        assert denied.post(path, json=body, headers=headers).status_code == 403
    monkeypatch.setattr(
        Recovery,
        "retry",
        lambda *args: (_ for _ in ()).throw(RecoveryUnavailable("private parser output")),
    )
    response = client.post(path, json=body, headers=headers)
    assert response.status_code == 503 and "private" not in response.text


@pytest.mark.postgres
def test_recovery_preserves_source_cursor_metadata_and_is_idempotent(database, tenant, monkeypatch):
    store, admin = database
    ctx, account = tenant
    receipt = held(store, ctx, account, monkeypatch)
    with store.transaction(ctx) as conn:
        raw_before = conn.execute("SELECT * FROM raw_objects").fetchall()
        events_before = conn.execute("SELECT * FROM provider_events").fetchall()
        cursor_before = conn.execute("SELECT * FROM sync_cursors").fetchall()
    result = retry(store, ctx, account, receipt)
    assert result["outcome"] == "recovered"
    assert result["historical_outcome"] is True and result["mailbox_effects"] is False
    assert retry(store, ctx, account, receipt) == result
    hits = store.search(ctx, SearchRequest(query="Melron"))
    assert len(hits) == 1 and hits[0]["evidence_id"] == result["evidence_id"]
    assert store.quarantines(ctx, account)["results"] == []
    with store.transaction(ctx) as conn:
        assert conn.execute("SELECT * FROM raw_objects").fetchall() == raw_before
        assert conn.execute("SELECT * FROM provider_events").fetchall() == events_before
        assert conn.execute("SELECT * FROM sync_cursors").fetchall() == cursor_before
        assert conn.execute("SELECT count(*) AS n FROM quarantine_receipts").fetchone()["n"] == 1
        assert conn.execute("SELECT count(*) AS n FROM recovery_attempts").fetchone()["n"] == 1
        projection = conn.execute("SELECT * FROM messages").fetchone()
        assert projection["provider_thread_id"] == "thread-1"
        assert projection["provider_metadata"] == {"mailbox_ids": ["inbox"], "keywords": ["$seen"]}
    with psycopg.connect(admin) as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM audit_events WHERE tenant_id=%s "
                "AND event_type='recovery.recovered'",
                (ctx.tenant_id,),
            ).fetchone()[0]
            == 1
        )
    # Cached successful receipt cannot resurrect a later deletion.
    store.ingest_page(ctx, account, "held", "deleted", [replace(pg.item("gone"), raw=None)])
    assert retry(store, ctx, account, receipt) == result
    assert store.search(ctx, SearchRequest(query="Melron")) == []


@pytest.mark.postgres
def test_failure_is_cached_per_parser_and_new_version_can_retry(database, tenant, monkeypatch):
    store, _ = database
    ctx, account = tenant
    receipt = held(store, ctx, account, monkeypatch)
    with monkeypatch.context() as patch:
        patch.setattr(persistence, "prepare_mime", lambda raw: (None, [], True))
        result = retry(store, ctx, account, receipt)
    assert result["outcome"] == "mime_rejected" and result["evidence_id"] is None
    assert retry(store, ctx, account, receipt) == result
    assert len(store.quarantines(ctx, account)["results"]) == 1
    monkeypatch.setattr(persistence, "PARSER_VERSION", "synthetic-fixed-v5")
    assert retry(store, ctx, account, receipt)["outcome"] == "recovered"


@pytest.mark.postgres
@pytest.mark.parametrize("change", ["deleted", "ready", "quarantined"])
def test_new_provider_event_during_parse_prevents_recovery(database, tenant, monkeypatch, change):
    store, _ = database
    ctx, account = tenant
    receipt = held(store, ctx, account, monkeypatch)
    real_prepare = persistence.prepare_mime

    def racing_parse(raw):
        with monkeypatch.context() as patch:
            patch.setattr(persistence, "prepare_mime", real_prepare)
            newer = replace(
                pg.item("newer"),
                raw=None
                if change == "deleted"
                else b""
                if change == "quarantined"
                else pg.item().raw,
            )
            store.ingest_page(ctx, account, "held", "newer", [newer])
        return real_prepare(raw)

    monkeypatch.setattr(persistence, "prepare_mime", racing_parse)
    with pytest.raises(Conflict):
        retry(store, ctx, account, receipt)
    with store.transaction(ctx) as conn:
        assert conn.execute("SELECT status FROM message_sync_state").fetchone()["status"] == change
        assert conn.execute("SELECT count(*) AS n FROM recovery_attempts").fetchone()["n"] == 0


@pytest.mark.postgres
def test_concurrent_retry_has_exactly_one_attempt(database, tenant, monkeypatch):
    store, _ = database
    ctx, account = tenant
    receipt = held(store, ctx, account, monkeypatch)
    barrier = Barrier(2)
    real_prepare = persistence.prepare_mime

    def simultaneous(raw):
        barrier.wait(timeout=10)
        return real_prepare(raw)

    monkeypatch.setattr(persistence, "prepare_mime", simultaneous)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: retry(store, ctx, account, receipt), range(2)))
    assert results[0] == results[1]
    with store.transaction(ctx) as conn:
        assert conn.execute("SELECT count(*) AS n FROM recovery_attempts").fetchone()["n"] == 1
        assert conn.execute("SELECT count(*) AS n FROM message_versions").fetchone()["n"] == 1


@pytest.mark.postgres
def test_parser_exception_and_publish_failure_leave_no_partial_writes(
    database, tenant, monkeypatch
):
    store, _ = database
    ctx, account = tenant
    receipt = held(store, ctx, account, monkeypatch)
    with monkeypatch.context() as patch:
        patch.setattr(
            persistence,
            "prepare_mime",
            lambda raw: (_ for _ in ()).throw(RuntimeError("private mail contents")),
        )
        with pytest.raises(RecoveryUnavailable) as exc:
            retry(store, ctx, account, receipt)
        assert "private" not in str(exc.value)
    with monkeypatch.context() as patch:
        patch.setattr(
            store,
            "record_attachments",
            lambda *args: (_ for _ in ()).throw(RuntimeError("synthetic crash")),
        )
        with pytest.raises(RuntimeError):
            retry(store, ctx, account, receipt)
    with store.transaction(ctx) as conn:
        for table in ("recovery_attempts", "messages", "message_versions", "attachment_receipts"):
            assert conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"] == 0
        assert (
            conn.execute("SELECT status FROM message_sync_state").fetchone()["status"]
            == "quarantined"
        )
    assert retry(store, ctx, account, receipt)["outcome"] == "recovered"


@pytest.mark.postgres
def test_wrong_account_tenant_membership_and_parser_cannot_retry(database, tenant, monkeypatch):
    store, _ = database
    ctx, account = tenant
    receipt = held(store, ctx, account, monkeypatch)
    with pytest.raises(NotFound):
        retry(store, ctx, uuid4(), receipt)
    with pytest.raises(NotFound):
        retry(store, ctx, account, uuid4())
    other_ctx, other_account = pg.tenant.__wrapped__(database)
    with pytest.raises(NotFound):
        retry(store, other_ctx, account, receipt)
    with pytest.raises(NotFound):
        retry(store, other_ctx, other_account, receipt)
    with pytest.raises(AccessDenied):
        retry(store, replace(ctx, actor_id=uuid4()), account, receipt)
    with pytest.raises(Conflict):
        Recovery(store).retry(Principal(ctx, "human"), account, receipt, "arbitrary-parser")


@pytest.mark.postgres
def test_current_search_excludes_old_parser_attachments_and_old_citations_survive(
    database, tenant, monkeypatch
):
    store, _ = database
    ctx, account = tenant
    mail = EmailMessage()
    mail["Subject"] = "Melron"
    mail.set_content("Synthetic body")
    mail.add_attachment("historicalattachmenttoken", filename="proof.txt")
    raw = mail.as_bytes()
    with monkeypatch.context() as patch:
        patch.setattr(persistence, "PARSER_VERSION", "synthetic-old-parser")
        store.ingest_page(ctx, account, None, "old", [replace(pg.item("old"), raw=raw)])
    old_hit = store.search(ctx, SearchRequest(query="historicalattachmenttoken"))[0]
    old_evidence = store.evidence(ctx, old_hit["evidence_id"])
    receipt = held(store, ctx, account, monkeypatch, raw=raw, cursor="old")
    real_prepare = persistence.prepare_mime

    def updated_parser(raw):
        normalized, attachments, rejected = real_prepare(raw)
        return (
            normalized,
            [replace(a, text="currentattachmenttoken") for a in attachments],
            rejected,
        )

    monkeypatch.setattr(persistence, "prepare_mime", updated_parser)
    result = retry(store, ctx, account, receipt)
    assert result["evidence_id"] != old_hit["evidence_id"]
    assert store.evidence(ctx, old_hit["evidence_id"]) == old_evidence
    assert store.search(ctx, SearchRequest(query="historicalattachmenttoken")) == []
    assert len(store.search(ctx, SearchRequest(query="currentattachmenttoken"))) == 1
    assert len(store.search(ctx, SearchRequest(query="Melron"))) == 1


@pytest.mark.postgres
def test_recovery_attempts_are_rls_isolated_and_immutable(database, tenant, monkeypatch):
    store, admin = database
    ctx, account = tenant
    receipt = held(store, ctx, account, monkeypatch, raw=b"")
    result = retry(store, ctx, account, receipt)
    other_ctx, _ = pg.tenant.__wrapped__(database)
    with store.transaction(other_ctx) as conn:
        assert (
            conn.execute("SELECT * FROM recovery_attempts WHERE id=%s", (result["id"],)).fetchall()
            == []
        )
    for verb in (
        "UPDATE recovery_attempts SET outcome='integrity_failed'",
        "DELETE FROM recovery_attempts",
    ):
        with pytest.raises(psycopg.errors.InsufficientPrivilege), store.transaction(ctx) as conn:
            conn.execute(verb)
        with pytest.raises(psycopg.errors.RaiseException), psycopg.connect(admin) as conn:
            conn.execute(verb + " WHERE id=%s", (result["id"],))


@pytest.mark.postgres
def test_hash_mismatch_never_parses_or_changes_quarantine(database, tenant, monkeypatch):
    store, admin = database
    ctx, account = tenant
    receipt = held(store, ctx, account, monkeypatch)
    # Deliberate at-rest corruption in this disposable synthetic tenant only.
    with psycopg.connect(admin) as conn:
        conn.execute("ALTER TABLE raw_objects DISABLE TRIGGER raw_append_only")
        conn.execute(
            "UPDATE raw_objects SET raw_mime=%s WHERE tenant_id=%s", (b"corrupt", ctx.tenant_id)
        )
        conn.execute("ALTER TABLE raw_objects ENABLE TRIGGER raw_append_only")

    def forbidden(raw):
        pytest.fail("corrupt bytes must not reach the parser")

    monkeypatch.setattr(persistence, "prepare_mime", forbidden)
    result = retry(store, ctx, account, receipt)
    assert result["outcome"] == "integrity_failed"
    assert result["evidence_id"] is None
    assert len(store.quarantines(ctx, account)["results"]) == 1


@pytest.mark.postgres
def test_legacy_receipt_does_not_reuse_stale_mailbox_metadata(database, tenant, monkeypatch):
    store, admin = database
    ctx, account = tenant
    store.ingest_page(ctx, account, None, "old", [replace(pg.item("old"), thread_id="stale")])
    receipt = held(store, ctx, account, monkeypatch, cursor="old")
    with psycopg.connect(admin) as conn:
        conn.execute("ALTER TABLE quarantine_receipts DISABLE TRIGGER quarantine_immutable")
        conn.execute("UPDATE quarantine_receipts SET source_metadata=NULL WHERE id=%s", (receipt,))
        conn.execute("ALTER TABLE quarantine_receipts ENABLE TRIGGER quarantine_immutable")
    assert retry(store, ctx, account, receipt)["outcome"] == "recovered"
    with store.transaction(ctx) as conn:
        row = conn.execute("SELECT provider_thread_id,provider_metadata FROM messages").fetchone()
        assert row == {
            "provider_thread_id": None,
            "provider_metadata": {"source_metadata": "unknown"},
        }


@pytest.mark.postgres
@pytest.mark.parametrize("revoke", ["account", "membership"])
def test_authorization_revoked_during_parse_cannot_publish(database, tenant, monkeypatch, revoke):
    store, admin = database
    ctx, account = tenant
    receipt = held(store, ctx, account, monkeypatch)
    real_prepare = persistence.prepare_mime

    def revoke_during_parse(raw):
        with psycopg.connect(admin) as conn:
            if revoke == "account":
                conn.execute("UPDATE mail_accounts SET status='disabled' WHERE id=%s", (account,))
            else:
                conn.execute("DELETE FROM tenant_memberships WHERE tenant_id=%s", (ctx.tenant_id,))
        return real_prepare(raw)

    monkeypatch.setattr(persistence, "prepare_mime", revoke_during_parse)
    with pytest.raises(NotFound if revoke == "account" else AccessDenied):
        retry(store, ctx, account, receipt)
    with psycopg.connect(admin) as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM recovery_attempts WHERE tenant_id=%s", (ctx.tenant_id,)
            ).fetchone()[0]
            == 0
        )


@pytest.mark.postgres
def test_populated_upgrade_preserves_immutable_evidence(database, tmp_path):
    from pathlib import Path

    from psycopg.types.json import Jsonb

    _, admin = database
    name = "email_brain_test_upgrade_" + uuid4().hex
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    dsn = make_conninfo(admin, dbname=name)
    try:
        directory = Path(__file__).resolve().parents[1] / "migrations"
        for path in sorted(directory.glob("000[1-7]_*.sql")):
            (tmp_path / path.name).write_bytes(path.read_bytes())
        migrate(dsn, tmp_path)
        with psycopg.connect(dsn) as reader:
            reader.execute("LOCK TABLE message_versions IN ACCESS SHARE MODE")
            with pytest.raises(psycopg.errors.LockNotAvailable):
                migrate(dsn, directory)
        tenant_id, account_id, message_id, version_id = (uuid4() for _ in range(4))
        snapshot = {"parser_version": "synthetic-old", "text": "unchanged"}
        with psycopg.connect(dsn) as conn:
            conn.execute(
                "INSERT INTO tenants(id,name) VALUES (%s,'Synthetic upgrade')", (tenant_id,)
            )
            conn.execute(
                "INSERT INTO mail_accounts(id,tenant_id,provider,address,secret_ref) "
                "VALUES (%s,%s,'fastmail','test@example.invalid','synthetic:none')",
                (account_id, tenant_id),
            )
            conn.execute(
                "INSERT INTO raw_objects(tenant_id,account_id,sha256,raw_mime) "
                "VALUES (%s,%s,%s,%s)",
                (tenant_id, account_id, "a" * 64, b"synthetic"),
            )
            conn.execute(
                "INSERT INTO messages(id,tenant_id,account_id,provider_message_id,provider_version,"
                "subject,sender,recipients,clean_text,raw_sha256,parser_version,received_at) "
                "VALUES (%s,%s,%s,'p1','v1','subject','test@example.invalid',"
                "'[]','unchanged',%s,'synthetic-old',now())",
                (message_id, tenant_id, account_id, "a" * 64),
            )
            conn.execute(
                "INSERT INTO message_versions(id,tenant_id,account_id,message_id,raw_sha256,"
                "provider_version,snapshot) "
                "VALUES (%s,%s,%s,%s,%s,'v1',%s)",
                (version_id, tenant_id, account_id, message_id, "a" * 64, Jsonb(snapshot)),
            )
        with psycopg.connect(dsn) as conn:
            conn.execute("UPDATE messages SET parser_version='mismatched-legacy'")
        with psycopg.connect(dsn) as writer:
            writer.execute("LOCK TABLE message_versions IN ROW EXCLUSIVE MODE")
            with pytest.raises(psycopg.errors.LockNotAvailable):
                migrate(dsn, directory)
        with pytest.raises(ValueError, match="0008_quarantine_recovery.sql rewrites populated"):
            migrate(dsn, directory)
        with pytest.raises(psycopg.errors.RaiseException, match="parser provenance mismatch"):
            migrate(dsn, directory, allow_populated_rewrite=True)
        with psycopg.connect(dsn) as conn:
            assert (
                conn.execute(
                    "SELECT count(*) FROM schema_migrations "
                    "WHERE name='0008_quarantine_recovery.sql'"
                ).fetchone()[0]
                == 0
            )
            conn.execute("UPDATE messages SET parser_version='synthetic-old'")
        rewrite_0008 = next(directory.glob("0008_*.sql"))
        (tmp_path / rewrite_0008.name).write_bytes(rewrite_0008.read_bytes())
        assert migrate(dsn, tmp_path, allow_populated_rewrite=True) == [
            "0008_quarantine_recovery.sql"
        ]
        with pytest.raises(ValueError, match="0009_external_raw_evidence.sql rewrites populated"):
            migrate(dsn, directory)
        with psycopg.connect(dsn) as conn:
            assert conn.execute(
                "SELECT count(*) FROM schema_migrations "
                "WHERE name='0009_external_raw_evidence.sql'"
            ).fetchone() == (0,)
        assert migrate(dsn, directory, allow_populated_rewrite=True) == [
            "0009_external_raw_evidence.sql",
            "0010_recovery_jobs.sql",
            "0011_processing_history.sql",
            "0012_document_jobs.sql",
            "0013_external_identities.sql",
            "0014_structured_memory.sql",
            "0015_datacore_persistence.sql",
            "0016_knowledgecore.sql",
            "0017_fileos_run_receipts.sql",
            "0018_fileos_inventory_reconciliation.sql",
            "0019_datacore_index_generations.sql",
            "0020_email_datacore_bridge.sql",
            "0021_email_attachment_bridge.sql",
            "0022_email_document_extraction_bridge.sql",
            "0023_archive_manifests.sql",
            "0024_archive_member_text_derivatives.sql",
            "0025_current_archive_derivative_search.sql",
            "0026_archive_member_documents.sql",
            "0027_current_archive_document_search.sql",
            "0028_archive_member_image_ocr.sql",
            "0029_migration_integrity_repair.sql",
            "0030_protected_record_truncate_guards.sql",
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
            "0055_knowledge_commitment_due.sql",
            "0056_knowledge_project_dossier.sql",
            "0057_private_statement_proposals.sql",
            "0058_fastmail_scoped_lease.sql",
            "0059_reviewed_project_aliases.sql",
            "0060_reviewed_project_members.sql",
            "0061_scoped_mailbox_exclusion.sql",
            "0062_excluded_email_evidence_visibility.sql",
            "0063_private_knowledge_proposal_batches.sql",
            "0064_private_statement_fileos_replay.sql",
            "0065_reviewed_project_artifacts.sql",
            "0066_reviewed_project_facts.sql",
            "0067_dossier_import_batch_binding.sql",
            "0068_dossier_proposal_citation_binding.sql",
            "0069_private_project_fact_proposals.sql",
            "0070_private_project_artifact_proposals.sql",
            "0071_reviewed_project_fact_measurements.sql",
            "0072_reviewed_project_fact_measurement_tokens.sql",
            "0073_project_fact_predicate_registry.sql",
            "0074_project_fact_predicate_latest_revision.sql",
            "0075_reviewed_source_tier_classifications.sql",
            "0076_source_tier_fileos_text_replay.sql",
            "0077_source_tier_email_text_replay.sql",
            "0078_source_tier_fileos_pdf_replay.sql",
            "0079_source_tier_email_pdf_replay.sql",
            "0080_email_pdf_replay_account_lock.sql",
            "0081_source_tier_fileos_xlsx_table_replay.sql",
            "0082_email_xlsx_extraction_approvals.sql",
            "0083_email_xlsx_extraction_results.sql",
            "0084_email_xlsx_document_bridge.sql",
        ]
        assert migrate(dsn, directory) == []
        with psycopg.connect(dsn) as conn:
            assert conn.execute(
                "SELECT id,snapshot,parser_version FROM message_versions"
            ).fetchone() == (version_id, snapshot, "synthetic-old")
        with pytest.raises(psycopg.errors.RaiseException), psycopg.connect(dsn) as conn:
            conn.execute("UPDATE message_versions SET snapshot='{}'")
    finally:
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


@pytest.mark.postgres
def test_policy_migration_preserves_unknown_legacy_receipt(database, tmp_path):
    from pathlib import Path

    _, admin = database
    name = "email_brain_test_policy_upgrade_" + uuid4().hex
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    dsn = make_conninfo(admin, dbname=name)
    try:
        directory = Path(__file__).resolve().parents[1] / "migrations"
        for path in sorted(directory.glob("[0-9][0-9][0-9][0-9]_*.sql")):
            if path.name not in {
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
                "0055_knowledge_commitment_due.sql",
                "0056_knowledge_project_dossier.sql",
                "0057_private_statement_proposals.sql",
                "0058_fastmail_scoped_lease.sql",
                "0059_reviewed_project_aliases.sql",
                "0060_reviewed_project_members.sql",
                "0061_scoped_mailbox_exclusion.sql",
                "0062_excluded_email_evidence_visibility.sql",
                "0063_private_knowledge_proposal_batches.sql",
                "0064_private_statement_fileos_replay.sql",
                "0065_reviewed_project_artifacts.sql",
                "0066_reviewed_project_facts.sql",
                "0067_dossier_import_batch_binding.sql",
                "0068_dossier_proposal_citation_binding.sql",
                "0069_private_project_fact_proposals.sql",
                "0070_private_project_artifact_proposals.sql",
                "0071_reviewed_project_fact_measurements.sql",
                "0072_reviewed_project_fact_measurement_tokens.sql",
                "0073_project_fact_predicate_registry.sql",
                "0074_project_fact_predicate_latest_revision.sql",
                "0075_reviewed_source_tier_classifications.sql",
                "0076_source_tier_fileos_text_replay.sql",
                "0077_source_tier_email_text_replay.sql",
                "0078_source_tier_fileos_pdf_replay.sql",
                "0079_source_tier_email_pdf_replay.sql",
                "0080_email_pdf_replay_account_lock.sql",
                "0081_source_tier_fileos_xlsx_table_replay.sql",
                "0082_email_xlsx_extraction_approvals.sql",
                "0083_email_xlsx_extraction_results.sql",
                "0084_email_xlsx_document_bridge.sql",
            }:
                (tmp_path / path.name).write_bytes(path.read_bytes())
        migrate(dsn, tmp_path)
        tenant_id, actor_id, run_id = uuid4(), uuid4(), uuid4()
        with psycopg.connect(dsn) as conn:
            conn.execute(
                "INSERT INTO tenants(id,name) VALUES (%s,'Synthetic policy upgrade')",
                (tenant_id,),
            )
            conn.execute(
                "INSERT INTO brain_sources(tenant_id,id,kind,display_name) "
                "VALUES (%s,'files_policy_upgrade','fileos','Synthetic')",
                (tenant_id,),
            )
            conn.execute(
                "INSERT INTO brain_fileos_run_receipts(tenant_id,actor_id,run_id,source_id,"
                "observed_at,manifest_sha256,code_revision,text_extractor_version,item_count,"
                "outcomes,published_documents) VALUES (%s,%s,%s,'files_policy_upgrade',now(),"
                "%s,'synthetic-old','fileos-text-v1',0,'{}'::jsonb,0)",
                (tenant_id, actor_id, run_id, "a" * 64),
            )
        assert migrate(dsn, directory) == [
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
            "0055_knowledge_commitment_due.sql",
            "0056_knowledge_project_dossier.sql",
            "0057_private_statement_proposals.sql",
            "0058_fastmail_scoped_lease.sql",
            "0059_reviewed_project_aliases.sql",
            "0060_reviewed_project_members.sql",
            "0061_scoped_mailbox_exclusion.sql",
            "0062_excluded_email_evidence_visibility.sql",
            "0063_private_knowledge_proposal_batches.sql",
            "0064_private_statement_fileos_replay.sql",
            "0065_reviewed_project_artifacts.sql",
            "0066_reviewed_project_facts.sql",
            "0067_dossier_import_batch_binding.sql",
            "0068_dossier_proposal_citation_binding.sql",
            "0069_private_project_fact_proposals.sql",
            "0070_private_project_artifact_proposals.sql",
            "0071_reviewed_project_fact_measurements.sql",
            "0072_reviewed_project_fact_measurement_tokens.sql",
            "0073_project_fact_predicate_registry.sql",
            "0074_project_fact_predicate_latest_revision.sql",
            "0075_reviewed_source_tier_classifications.sql",
            "0076_source_tier_fileos_text_replay.sql",
            "0077_source_tier_email_text_replay.sql",
            "0078_source_tier_fileos_pdf_replay.sql",
            "0079_source_tier_email_pdf_replay.sql",
            "0080_email_pdf_replay_account_lock.sql",
            "0081_source_tier_fileos_xlsx_table_replay.sql",
            "0082_email_xlsx_extraction_approvals.sql",
            "0083_email_xlsx_extraction_results.sql",
            "0084_email_xlsx_document_bridge.sql",
        ]
        with psycopg.connect(dsn) as conn:
            assert conn.execute(
                "SELECT policy_sha256,root_binding_sha256 FROM brain_fileos_run_receipts "
                "WHERE tenant_id=%s AND actor_id=%s AND run_id=%s",
                (tenant_id, actor_id, run_id),
            ).fetchone() == (None, None)
            assert conn.execute(
                "SELECT root_binding_sha256 FROM brain_sources "
                "WHERE tenant_id=%s AND id='files_policy_upgrade'",
                (tenant_id,),
            ).fetchone() == (None,)
        with pytest.raises(psycopg.errors.RaiseException), psycopg.connect(dsn) as conn:
            conn.execute(
                "UPDATE brain_fileos_run_receipts SET policy_sha256=%s "
                "WHERE tenant_id=%s AND actor_id=%s AND run_id=%s",
                ("c" * 64, tenant_id, actor_id, run_id),
            )
        with pytest.raises(psycopg.errors.CheckViolation), psycopg.connect(dsn) as conn:
            conn.execute(
                "INSERT INTO brain_fileos_run_receipts(tenant_id,actor_id,run_id,source_id,"
                "observed_at,manifest_sha256,code_revision,text_extractor_version,item_count,"
                "outcomes,published_documents) VALUES (%s,%s,%s,'files_policy_upgrade',now(),"
                "%s,'synthetic-new','fileos-text-v1',0,'{}'::jsonb,0)",
                (tenant_id, actor_id, uuid4(), "b" * 64),
            )
        with pytest.raises(psycopg.errors.RaiseException), psycopg.connect(dsn) as conn:
            conn.execute(
                "UPDATE brain_sources SET root_binding_sha256=%s "
                "WHERE tenant_id=%s AND id='files_policy_upgrade'",
                ("d" * 64, tenant_id),
            )
        with pytest.raises(psycopg.errors.RaiseException), psycopg.connect(dsn) as conn:
            conn.execute(
                "INSERT INTO brain_sources(tenant_id,id,kind,display_name) "
                "VALUES (%s,'files_new_without_root','fileos','Synthetic')",
                (tenant_id,),
            )
        with pytest.raises(psycopg.errors.CheckViolation), psycopg.connect(dsn) as conn:
            conn.execute(
                "INSERT INTO brain_fileos_run_receipts(tenant_id,actor_id,run_id,source_id,"
                "observed_at,manifest_sha256,policy_sha256,code_revision,"
                "text_extractor_version,item_count,outcomes,published_documents) "
                "VALUES (%s,%s,%s,'files_policy_upgrade',now(),%s,%s,"
                "'synthetic-new','fileos-text-v1',0,'{}'::jsonb,0)",
                (tenant_id, actor_id, uuid4(), "b" * 64, "c" * 64),
            )
    finally:
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


@pytest.mark.postgres
def test_archive_ledger_migration_refuses_preexisting_child_drift(database, tmp_path):
    from pathlib import Path

    _, admin = database
    name = "email_brain_test_archive_ledger_" + uuid4().hex
    role = "test_archive_" + uuid4().hex[:12]
    password = "synthetic-" + uuid4().hex
    role_created = False
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    dsn = make_conninfo(admin, dbname=name)
    try:
        directory = Path(__file__).resolve().parents[1] / "migrations"
        pre_upgrade = tmp_path / "pre_upgrade"
        pre_upgrade.mkdir()
        for path in sorted(directory.glob("[0-9][0-9][0-9][0-9]_*.sql")):
            if path.name not in {
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
            "0055_knowledge_commitment_due.sql",
            "0056_knowledge_project_dossier.sql",
            "0057_private_statement_proposals.sql",
            "0058_fastmail_scoped_lease.sql",
            "0059_reviewed_project_aliases.sql",
            "0060_reviewed_project_members.sql",
            "0061_scoped_mailbox_exclusion.sql",
            "0062_excluded_email_evidence_visibility.sql",
            "0063_private_knowledge_proposal_batches.sql",
            "0064_private_statement_fileos_replay.sql",
            "0065_reviewed_project_artifacts.sql",
            "0066_reviewed_project_facts.sql",
            "0067_dossier_import_batch_binding.sql",
            "0068_dossier_proposal_citation_binding.sql",
            "0069_private_project_fact_proposals.sql",
            "0070_private_project_artifact_proposals.sql",
            "0071_reviewed_project_fact_measurements.sql",
            "0072_reviewed_project_fact_measurement_tokens.sql",
            "0073_project_fact_predicate_registry.sql",
            "0074_project_fact_predicate_latest_revision.sql",
            "0075_reviewed_source_tier_classifications.sql",
            "0076_source_tier_fileos_text_replay.sql",
            "0077_source_tier_email_text_replay.sql",
            "0078_source_tier_fileos_pdf_replay.sql",
            "0079_source_tier_email_pdf_replay.sql",
            "0080_email_pdf_replay_account_lock.sql",
            "0081_source_tier_fileos_xlsx_table_replay.sql",
            "0082_email_xlsx_extraction_approvals.sql",
            "0083_email_xlsx_extraction_results.sql",
            "0084_email_xlsx_document_bridge.sql",
            }:
                (pre_upgrade / path.name).write_bytes(path.read_bytes())
        migrate(dsn, pre_upgrade)
        with psycopg.connect(dsn) as conn:
            conn.execute(
                sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD {}").format(
                    sql.Identifier(role), sql.Literal(password)
                )
            )
            # This fixture intentionally stops before 0033. Grant only tables
            # present at that historical point; the normal grant_runtime()
            # must continue to fail on an incompletely migrated live schema.
            present = {
                row[0] for row in conn.execute(
                    "SELECT tablename FROM pg_tables WHERE schemaname='public'"
                )
            }
            conn.execute(
                sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role))
            )
            for privilege, tables in (
                ("SELECT", RUNTIME_SELECT),
                ("INSERT", RUNTIME_INSERT),
                ("UPDATE", ("brain_sources", "brain_source_items", "brain_jobs")),
            ):
                available = [table for table in tables if table in present]
                conn.execute(
                    sql.SQL("GRANT {} ON {} TO {}").format(
                        sql.SQL(privilege),
                        sql.SQL(",").join(map(sql.Identifier, available)),
                        sql.Identifier(role),
                    )
                )
        role_created = True
        tenant_id, actor_id = uuid4(), uuid4()
        with psycopg.connect(dsn) as conn:
            conn.execute(
                "INSERT INTO tenants(id,name) VALUES (%s,'Synthetic archive upgrade')",
                (tenant_id,),
            )
            conn.execute(
                "INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES (%s,%s,'owner')",
                (tenant_id, actor_id),
            )
        ctx = pg.datacore_context(pg.TenantContext(tenant_id, actor_id, frozenset(), uuid4()))
        core = pg.DataCoreStore(Store(make_conninfo(dsn, user=role, password=password)))
        archive_root = tmp_path / "archive"
        archive_root.mkdir()
        _, _, result = pg.archive_fixture(
            core, ctx, archive_root, source_id="files_archive_upgrade"
        )
        recorded = core.record_archive_inventory(ctx, result, pg.ARCHIVE_PROCESSOR, uuid4())
        with psycopg.connect(dsn) as conn:
            conn.execute(
                "INSERT INTO brain_archive_skips "
                "(tenant_id,inventory_id,ordinal,locator,reason,depth) "
                "VALUES (%s,%s,2000,'late.skip','unreadable',0)",
                (tenant_id, recorded.inventory_id),
            )
        with pytest.raises(
            psycopg.errors.RaiseException, match="existing archive inventory ledger"
        ):
            migrate(dsn, directory)
        with psycopg.connect(dsn) as conn:
            assert (
                conn.execute(
                    "SELECT count(*) FROM brain_archive_skips "
                    "WHERE tenant_id=%s AND inventory_id=%s",
                    (tenant_id, recorded.inventory_id),
                ).fetchone()[0]
                == 1
            )
            assert (
                conn.execute(
                    "SELECT count(*) FROM schema_migrations "
                    "WHERE name='0033_archive_ledger_parent_integrity.sql'"
                ).fetchone()[0]
                == 0
            )
    finally:
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
            if role_created:
                conn.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))
