"""Regression proofs from review: fake issuer and fictional MIME only."""

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from uuid import uuid4

import psycopg
import pytest
import test_oidc as oidc
import test_postgres as pg
from test_rule_control import approved

from email_brain.auth import AuthenticationUnavailable, Principal
from email_brain.mime_sandbox import decode_response, process_raw
from email_brain.rules.active import classify
from email_brain.rules.control import RuleControl
from email_brain.schemas import SearchRequest
from email_brain.store import prepare_mime

keys = oidc.keys
database, tenant = pg.database, pg.tenant


@pytest.mark.parametrize("failure", [False, True])
def test_cached_key_does_not_wait_for_unknown_key_refresh(keys, monkeypatch, failure):
    issuer = oidc.FakeIssuer(keys[0])
    verifier = issuer.verifier()
    valid = oidc.token(keys[0], issuer.config)
    assert verifier.verify(valid)
    issuer.now = 31
    entered, release = threading.Event(), threading.Event()
    original = verifier._refresh

    def delayed():
        entered.set()
        assert release.wait(3)
        if failure:
            raise ValueError("fictional issuer outage")
        return original()

    monkeypatch.setattr(verifier, "_refresh", delayed)
    unknown = oidc.token(keys[1], issuer.config, headers={"kid": "unknown"})
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(verifier.verify, unknown)
        assert entered.wait(1)
        cached = pool.submit(verifier.verify, valid)
        try:
            assert cached.result(timeout=1) is not None
        finally:
            release.set()
        if failure:
            with pytest.raises(AuthenticationUnavailable):
                pending.result(timeout=2)
        else:
            assert pending.result(timeout=2) is None
    assert verifier.verify(valid)


CASES = [
    ("From: person@example.invalid", True),
    ('From: "Last, First" <person@example.invalid>', True),
    ("From: Person (comment) <person@example.invalid>", True),
    ("From: Person\r\n <person@example.invalid>", True),
    ("From: person@example.invalid, other@other.invalid", False),
    ("From: person@example.invalid\r\nFrom: other@other.invalid", False),
    ("From: person@example.invalid\r\nFrom: person@example.invalid", False),
    ("From: Team: person@example.invalid;", False),
    ("From: Person <person@example.invalid", False),
    ("From: person@example.invalid trailing", False),
    ("From: localonly", False),
    ("From: <>", False),
    ("", False),
    ("From: " + "p" * 310 + "@example.invalid", False),
]


def source(header):
    return (
        (header + "\r\n" if header else "") + "Subject: Melron\r\n\r\nFictional body retained."
    ).encode()


@pytest.mark.parametrize("header,eligible", CASES)
@pytest.mark.parametrize("isolated", [False, True])
def test_source_sender_eligibility(header, eligible, isolated):
    raw = source(header)
    message, _, rejected = decode_response(process_raw(raw), raw) if isolated else prepare_mime(raw)
    assert not rejected and message is not None
    assert message.text == "Fictional body retained."
    assert message.sender_rule_eligible is eligible
    rule = {
        "proposal_id": str(uuid4()),
        "version": 1,
        "payload": {
            "kind": "rule",
            "sender_domain": "example.invalid",
            "category": "test",
            "canonical_mailbox": "needs_reply",
        },
    }
    result = classify([rule], 1, message.sender if message.sender_rule_eligible else "")
    assert bool(result["effects"]) is eligible


def test_legacy_worker_never_infers_sender_eligibility():
    raw = source("From: person@example.invalid")
    data = json.loads(process_raw(raw))
    data["normalized"].pop("sender_rule_eligible", None)
    result, _, rejected = decode_response(json.dumps(data).encode(), raw)
    assert not rejected and result.sender_rule_eligible is False


@pytest.mark.postgres
@pytest.mark.parametrize("header,eligible", [CASES[0], CASES[4], CASES[5]])
def test_sender_rules_use_source_eligibility_in_sql(database, tenant, header, eligible):
    store, _ = database
    ctx, account = tenant
    raw = source(header)
    store.ingest_page(ctx, account, None, "s1", [replace(pg.item(), raw=raw)])
    human, control = Principal(ctx, "human"), RuleControl(store)
    proposal = approved(store, ctx)
    receipt = control.simulate(human, proposal["id"], 2)
    assert bool(receipt["sample"][0]["after"]) is eligible
    control.activate(human, receipt["id"])
    hit = store.search(ctx, SearchRequest(query="Melron"))[0]
    assert bool(hit["classification"]["effects"]) is eligible
    assert "sender_rule_eligible" not in hit
    evidence = store.evidence(ctx, hit["evidence_id"])
    assert "sender_rule_eligible" not in evidence
    assert evidence["excerpt"] == "Fictional body retained."
    assert store.load_raw(ctx, account, evidence["raw_sha256"]) == raw


@pytest.mark.postgres
@pytest.mark.parametrize("flag", [None, False, "true", 1, True])
def test_legacy_snapshot_and_strict_boolean_gate(database, tenant, flag):
    store, admin = database
    ctx, account = tenant
    store.ingest_page(ctx, account, None, "s1", [pg.item()])
    # Append a synthetic historical snapshot; never rewrite immutable evidence.
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO message_versions(tenant_id,account_id,message_id,raw_sha256,"
            "provider_version,snapshot) SELECT tenant_id,account_id,message_id,raw_sha256,"
            "provider_version,(snapshot - 'sender_rule_eligible') || "
            "jsonb_build_object('parser_version','legacy-review') || %s::jsonb "
            "FROM message_versions WHERE tenant_id=%s",
            (json.dumps({} if flag is None else {"sender_rule_eligible": flag}), ctx.tenant_id),
        )
        conn.execute(
            "UPDATE messages SET parser_version='legacy-review' WHERE tenant_id=%s",
            (ctx.tenant_id,),
        )
    human, control = Principal(ctx, "human"), RuleControl(store)
    proposal = approved(store, ctx)
    receipt = control.simulate(human, proposal["id"], 2)
    assert bool(receipt["sample"][0]["after"]) is (flag is True)
    control.activate(human, receipt["id"])
    result = store.search(ctx, SearchRequest(query="Melron"))[0]
    assert bool(result["classification"]["effects"]) is (flag is True)
    assert "sender_rule_eligible" not in result


@pytest.mark.parametrize("bad", [None, 0, 1, "true", [], {}])
def test_worker_sender_flag_is_strict_boolean(bad):
    from email_brain.mime_sandbox import MimeUnavailable

    raw = source("From: person@example.invalid")
    data = json.loads(process_raw(raw))
    data["normalized"]["sender_rule_eligible"] = bad
    with pytest.raises(MimeUnavailable):
        decode_response(json.dumps(data).encode(), raw)


@pytest.mark.parametrize("expired", [False, True])
def test_refresh_waiter_timeout_never_returns_expired_key(keys, monkeypatch, expired):
    issuer = oidc.FakeIssuer(keys[0])
    verifier = issuer.verifier()
    token = oidc.token(keys[0], issuer.config)
    assert verifier.verify(token)
    issuer.now = 301 if expired else 31
    verifier._refreshing = True
    waits = []

    def timeout(predicate, timeout):
        waits.append(timeout)
        return False

    monkeypatch.setattr(verifier._changed, "wait_for", timeout)
    with pytest.raises(AuthenticationUnavailable):
        verifier.verify(
            token if expired else oidc.token(keys[1], issuer.config, headers={"kid": "new"})
        )
    assert waits == [5]
    assert len(issuer.urls) == 2


@pytest.mark.parametrize("failure", [False, True])
def test_refresh_single_flight_waiters_recheck_expiry_and_rotation(keys, monkeypatch, failure):
    issuer = oidc.FakeIssuer(keys[0])
    verifier = issuer.verifier()
    old = oidc.token(keys[0], issuer.config)
    new = oidc.token(keys[1], issuer.config, headers={"kid": "new"})
    assert verifier.verify(old)
    issuer.now = 301
    issuer.entries = [issuer.jwk(keys[1], "new")]
    entered, waiting, release = threading.Event(), threading.Event(), threading.Event()
    refresh, wait_for = verifier._refresh, verifier._changed.wait_for
    calls = []

    def delayed():
        calls.append(1)
        entered.set()
        assert release.wait(3)
        if failure:
            raise ValueError("fictional failure")
        return refresh()

    def wait(predicate, timeout):
        waiting.set()
        return wait_for(predicate, timeout)

    monkeypatch.setattr(verifier, "_refresh", delayed)
    monkeypatch.setattr(verifier._changed, "wait_for", wait)
    with ThreadPoolExecutor(max_workers=2) as pool:
        owner = pool.submit(verifier.verify, new)
        assert entered.wait(1)
        follower = pool.submit(verifier.verify, old)
        try:
            assert waiting.wait(1)
        finally:
            release.set()
        if failure:
            for future in (owner, follower):
                with pytest.raises(AuthenticationUnavailable):
                    future.result(timeout=2)
        else:
            assert owner.result(timeout=2)
            assert follower.result(timeout=2) is None
    assert calls == [1]
    assert verifier._refreshing is False


@pytest.mark.postgres
@pytest.mark.parametrize("kind", ["attachment", "document"])
@pytest.mark.parametrize("ambiguous", [False, True])
def test_attachment_and_pdf_search_apply_same_sender_gate(database, tenant, kind, ambiguous):
    from email.message import EmailMessage

    from pdf_samples import mail_packet, variant
    from test_document_jobs import POLICY, VERSION, FakePdf, worker_principal

    from email_brain.document_jobs import DocumentJobs

    store, admin = database
    ctx, account = tenant
    if kind == "document":
        raw, _, _ = mail_packet(variant("text"))
        query = "pdfonlyproof"
    else:
        mail = EmailMessage()
        mail["From"] = "sender@example.invalid"
        mail["Subject"] = "Synthetic attachment"
        mail.set_content("Fictional body")
        mail.add_attachment("attachmentonlyproof", subtype="plain", filename="notes.txt")
        raw, query = mail.as_bytes(), "attachmentonlyproof"
    if ambiguous:
        raw = b"From: other@other.invalid\r\n" + raw
    store.ingest_page(ctx, account, None, "s1", [replace(pg.item(), raw=raw)])
    human, control = Principal(ctx, "human"), RuleControl(store)
    proposal = approved(store, ctx)
    preview = control.simulate(human, proposal["id"], 2)
    control.activate(human, preview["id"])
    if kind == "document":
        with store.transaction(ctx) as conn:
            receipt = conn.execute("SELECT id FROM attachment_receipts").fetchone()["id"]
        jobs = DocumentJobs(store, VERSION)
        jobs.enqueue(human, account, receipt, VERSION, POLICY, uuid4())
        base = worker_principal(admin, ctx)
        worker = replace(
            base, context=replace(base.context, scopes=frozenset({"email.document.process"}))
        )
        assert jobs.run_once(worker, account, FakePdf())["status"] == "completed"
    results = store.search(ctx, SearchRequest(query=query, include_documents=kind == "document"))
    assert len(results) == 1 and results[0]["result_type"] == kind
    assert bool(results[0]["classification"]["effects"]) is not ambiguous
    assert "sender_rule_eligible" not in results[0]
