"""Actual PostgreSQL/API/owner-reader checks, disposable synthetic evidence only."""

import hashlib
import json
import subprocess
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
import test_postgres as pg
from fastapi.testclient import TestClient
from test_isolated_recovery import VERSION, FakeProcessor
from test_large_evidence import external as external
from test_message_reader import mail_bytes

from email_brain.api import create_app
from email_brain.auth import Credential, Principal, TokenRegistry
from email_brain.blobs import BlobError
from email_brain.message_reader import MessageReader
from email_brain.normalize import MAX_RAW_BYTES
from email_brain.recovery import Recovery
from email_brain.schemas import SearchRequest
from email_brain.store import AccessDenied, Conflict, NotFound

database, tenant = pg.database, pg.tenant
pytestmark = pytest.mark.postgres
TOKEN = "synthetic-reader-sql-test-only-00000000000"


def client(store, ctx, kind="human"):
    credential = Credential(
        token_sha256=hashlib.sha256(TOKEN.encode()).hexdigest(),
        tenant_id=ctx.tenant_id,
        actor_id=ctx.actor_id,
        scopes={"email.evidence.read", "email.search"},
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
        client_kind=kind,
    )
    return TestClient(
        create_app(store, TokenRegistry([credential])), headers={"Authorization": f"Bearer {TOKEN}"}
    )


def ingest(store, ctx, account, raw=None):
    raw = raw or mail_bytes(
        "Readerproof " + "x" * 130000 + " FINALTAIL",
        attachments=[
            ("../costs.csv", b"name,cost\nA,123\n", "text/csv"),
            ("bad.html", b"<script>do_not_execute()</script>", "text/html"),
        ],
    )
    store.ingest_page(ctx, account, None, "r1", [replace(pg.item(), raw=raw)])
    evidence = store.search(ctx, SearchRequest(query="Readerproof"))[0]["evidence_id"]
    return evidence, raw


def test_full_body_and_exact_exports_with_audit_no_source_mutation(database, tenant):
    store, admin = database
    ctx, account = tenant
    evidence, raw = ingest(store, ctx, account)
    api = client(store, ctx)
    path = f"/v1/reader/{evidence}"
    result = api.get(path)
    assert result.status_code == 200
    data = result.json()
    assert data["body"].endswith("FINALTAIL") and len(data["body"]) > 130000
    assert data["body_complete"] and data["body_source"] == "original_mime"
    assert len(api.get(f"/v1/evidence/{evidence}").json()["excerpt"]) == 4000
    before = store.evidence(ctx, evidence)
    original = api.post(path + "/original", json={"acknowledge_unscanned": True})
    assert original.status_code == 200 and original.content == raw
    for part in data["attachments"]:
        downloaded = api.post(
            path + f"/attachments/{part['id']}", json={"acknowledge_unscanned": True}
        )
        assert downloaded.status_code == 200
        assert downloaded.headers["content-type"] == "application/octet-stream"
        assert downloaded.headers["content-disposition"].endswith('.bin"')
        assert hashlib.sha256(downloaded.content).hexdigest() == part["sha256"]
        assert len(downloaded.content) == part["byte_size"]
    assert store.evidence(ctx, evidence) == before
    # Runtime deliberately writes but cannot browse audit records. Inspect the
    # synthetic receipt with the separate administrator, never broaden its grant.
    with psycopg.connect(admin) as conn:
        events = conn.execute(
            "SELECT event_type FROM audit_events WHERE tenant_id=%s "
            "AND event_type LIKE 'message.%%'",
            (ctx.tenant_id,),
        ).fetchall()
        assert sorted(e[0] for e in events) == [
            "message.attachment_export",
            "message.attachment_export",
            "message.original_export",
            "message.read",
        ]
    with pytest.raises(psycopg.errors.InsufficientPrivilege), store.transaction(ctx) as conn:
        conn.execute("SELECT event_type FROM audit_events")
    with store.transaction(ctx) as conn:
        assert conn.execute("SELECT count(*) AS n FROM provider_events").fetchone()["n"] == 1


def test_actual_api_reader_shape_and_bytes_pass_node_ui(database, tenant):
    store, _ = database
    ctx, account = tenant
    evidence, _ = ingest(store, ctx, account)
    api = client(store, ctx)
    search = api.post("/v1/search", json={"query": "Readerproof"}).json()
    reader = api.get(f"/v1/reader/{evidence}").json()
    packet = {"search": search, "reader": reader}
    run = subprocess.run(
        ["node", "tests/web_reader_api_contract.cjs"],
        cwd=Path(__file__).resolve().parents[1],
        input=json.dumps(packet),
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    assert run.stdout.startswith("PASS: actual reader API")


@pytest.mark.parametrize("mode", ["tenant", "member", "scope", "assistant", "worker", "inactive"])
def test_unauthorized_reader_and_exports_fail_closed(database, tenant, mode):
    store, admin = database
    ctx, account = tenant
    evidence, _ = ingest(store, ctx, account)
    reader = MessageReader(store)
    denied = Principal(ctx, mode if mode in {"assistant", "worker"} else "human")
    expected = AccessDenied
    if mode == "tenant":
        denied = replace(denied, context=replace(ctx, tenant_id=uuid4()))
    if mode == "scope":
        denied = replace(denied, context=replace(ctx, scopes=frozenset({"email.search"})))
    if mode in {"member", "inactive"}:
        with psycopg.connect(admin) as conn:
            if mode == "member":
                conn.execute(
                    "UPDATE tenant_memberships SET role='member' WHERE tenant_id=%s",
                    (ctx.tenant_id,),
                )
            else:
                conn.execute("UPDATE mail_accounts SET status='paused' WHERE id=%s", (account,))
                expected = NotFound
    for operation in (reader.read, reader.download):
        with pytest.raises(expected):
            operation(denied, evidence)


def test_foreign_valid_owner_cannot_address_other_tenant_evidence(database, tenant):
    store, admin = database
    ctx, account = tenant
    evidence, _ = ingest(store, ctx, account)
    other = replace(ctx, tenant_id=uuid4(), actor_id=uuid4())
    with psycopg.connect(admin) as conn:
        conn.execute("INSERT INTO tenants(id,name) VALUES (%s,'Reader other')", (other.tenant_id,))
        conn.execute(
            "INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES (%s,%s,'owner')",
            (other.tenant_id, other.actor_id),
        )
    reader = MessageReader(store)
    for operation in (reader.read, reader.download):
        with pytest.raises(NotFound):
            operation(Principal(other, "human"), evidence)


def test_receipt_must_belong_to_exact_evidence(database, tenant):
    store, _ = database
    ctx, account = tenant
    evidence, raw = ingest(store, ctx, account)
    store.ingest_page(
        ctx, account, "r1", "r2", [replace(pg.item("another"), provider_id="another", raw=raw)]
    )
    reader = MessageReader(store)
    hits = store.search(ctx, SearchRequest(query="Readerproof"))
    other = next(h["evidence_id"] for h in hits if h["evidence_id"] != evidence)
    receipt = reader.read(Principal(ctx, "human"), other)["attachments"][0]["id"]
    with pytest.raises(NotFound):
        reader.download(Principal(ctx, "human"), evidence, receipt)


@pytest.mark.parametrize("change", ["updated", "deleted"])
def test_historical_evidence_download_is_version_stable(database, tenant, change):
    store, _ = database
    ctx, account = tenant
    evidence, raw = ingest(store, ctx, account)
    store.ingest_page(
        ctx,
        account,
        "r1",
        "r2",
        [
            replace(
                pg.item("next"),
                raw=None if change == "deleted" else mail_bytes("Readerproof replacement"),
            )
        ],
    )
    reader = MessageReader(store)
    assert reader.download(Principal(ctx, "human"), evidence)[0] == raw
    assert reader.read(Principal(ctx, "human"), evidence)["body"].endswith("FINALTAIL")


@pytest.mark.parametrize("operation", ["read", "download"])
def test_changed_bytes_are_never_displayed_or_exported(database, tenant, monkeypatch, operation):
    store, _ = database
    ctx, account = tenant
    evidence, _ = ingest(store, ctx, account)
    monkeypatch.setattr(store, "load_raw", lambda *args: b"corrupt")
    with pytest.raises(BlobError):
        getattr(MessageReader(store), operation)(Principal(ctx, "human"), evidence)


@pytest.mark.parametrize("operation", ["read", "download"])
@pytest.mark.parametrize("revoke", ["account", "owner"])
def test_access_is_rechecked_after_loading_bytes(database, tenant, monkeypatch, operation, revoke):
    store, admin = database
    ctx, account = tenant
    evidence, _ = ingest(store, ctx, account)
    original = store.load_raw

    def revoked(*args):
        raw = original(*args)
        with psycopg.connect(admin) as conn:
            if revoke == "account":
                conn.execute("UPDATE mail_accounts SET status='paused' WHERE id=%s", (account,))
            else:
                conn.execute("DELETE FROM tenant_memberships WHERE tenant_id=%s", (ctx.tenant_id,))
        return raw

    monkeypatch.setattr(store, "load_raw", revoked)
    with pytest.raises(NotFound if revoke == "account" else AccessDenied):
        getattr(MessageReader(store), operation)(Principal(ctx, "human"), evidence)


def test_encrypted_small_source_has_identical_reader_and_export(external, tenant):
    ctx, account = tenant
    evidence, raw = ingest(external, ctx, account)
    reader = MessageReader(external)
    assert reader.read(Principal(ctx, "human"), evidence)["body"].endswith("FINALTAIL")
    assert reader.download(Principal(ctx, "human"), evidence)[0] == raw


def test_large_projection_discloses_truncation_and_exports_original_without_api_parse(
    external, tenant, monkeypatch
):
    ctx, account = tenant
    raw = mail_bytes(
        "Readerproof " + "x" * MAX_RAW_BYTES + " LASTBYTE",
        attachments=[("file.txt", b"part", "text/plain")],
    )
    external.ingest_page(ctx, account, None, "large", [replace(pg.item(), raw=raw)])
    receipt = external.quarantines(ctx, account)["results"][0]["id"]
    result = Recovery(external, processor=FakeProcessor()).retry(
        Principal(ctx, "human"), account, receipt, VERSION
    )
    assert result["outcome"] == "recovered"
    evidence = result["evidence_id"]
    monkeypatch.setattr(
        "email_brain.message_reader.parse_small", lambda _: pytest.fail("large API parsing")
    )
    reader = MessageReader(external)
    data = reader.read(Principal(ctx, "human"), evidence)
    assert data["body_source"] == "stored_projection" and not data["body_complete"]
    assert len(data["body"]) == 100000
    assert data["headers_truncated"] and data["headers"] == []
    assert reader.download(Principal(ctx, "human"), evidence)[0] == raw
    assert not data["attachments"][0]["download_available"]
    with pytest.raises(Conflict):
        reader.download(Principal(ctx, "human"), evidence, data["attachments"][0]["id"])
