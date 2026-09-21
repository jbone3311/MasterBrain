"""Synthetic adversarial checks; no external providers, credentials or mailbox writes."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from test_postgres import database as database
from test_postgres import tenant as tenant
from test_service import TOKEN, registry

from email_brain.api import create_app
from email_brain.auth import TokenRegistry
from email_brain.cli import seed, seed_corpus
from email_brain.schemas import SearchRequest
from email_brain.store import AccessDenied, IngestItem, NotFound, Store, prepare_mime

POISON_MIME = [
    pytest.param(
        b"Content-Type: text/plain; charset=utf-7\r\n"
        b"Content-Disposition: attachment; filename=a.txt\r\n\r\nhello+AAA-world",
        id="attachment-decoded-nul",
    ),
    pytest.param(
        b"Content-Type: text/plain; charset=unicode_escape\r\n"
        b"Content-Disposition: attachment; filename=a.txt\r\n\r\nhello\\x00world",
        id="attachment-escaped-nul",
    ),
    pytest.param(
        b"Content-Type: text/plain; charset=unicode_escape\r\n"
        b"Content-Disposition: attachment; filename=a.txt\r\n\r\nhello\\ud800world",
        id="attachment-decoded-surrogate",
    ),
    pytest.param(
        b"Content-Type: text/plain; charset=unicode_escape\r\n\r\nhello\\ud800world",
        id="body-decoded-surrogate",
    ),
    pytest.param(
        b"Content-Type: text/x\x00evil\r\nContent-Disposition: attachment; filename=a.bin\r\n\r\nx",
        id="attachment-media-type-nul",
    ),
]


@pytest.mark.parametrize("raw", POISON_MIME)
def test_mime_is_quarantined_or_all_projections_are_postgres_safe(raw):
    """Python codecs can create NUL/surrogates that are absent from raw payload bytes."""
    normalized, attachments, quarantined = prepare_mime(raw)
    if quarantined:
        assert normalized is None and attachments == []
        return
    assert normalized is not None
    values = [
        normalized.subject,
        normalized.sender,
        *normalized.recipients,
        normalized.internet_message_id or "",
        normalized.text,
    ]
    for attachment in attachments:
        values.extend(
            [
                attachment.original_filename,
                attachment.safe_filename,
                attachment.media_type,
                attachment.text,
            ]
        )
    for value in values:
        assert "\x00" not in value
        value.encode("utf-8", errors="strict")
    assert normalized.raw_sha256 == hashlib.sha256(raw).hexdigest()


@pytest.mark.postgres
@pytest.mark.parametrize("raw", POISON_MIME)
def test_poison_mail_mixed_with_good_mail_commits_raw_and_checkpoint(database, tenant, raw):
    store, _ = database
    context, account = tenant
    good = IngestItem(
        "good-event",
        "good-provider-id",
        "good-version",
        datetime(2026, 9, 20, tzinfo=UTC),
        b"Subject: Stablecanary\r\n\r\nStablecanary independent valid evidence",
    )
    poison = replace(good, event_key="poison-event", provider_id="poison-provider-id", raw=raw)
    assert store.ingest_page(context, account, None, "committed", [poison, good]) == 2
    assert store.ingest_page(context, account, None, "committed", [poison, good]) == 0
    hits = store.search(context, SearchRequest(query="Stablecanary"))
    assert len(hits) == 1
    assert store.evidence(context, hits[0]["evidence_id"])["untrusted_content"]
    with store.transaction(context) as connection:
        saved = connection.execute(
            "SELECT raw_mime FROM raw_objects WHERE account_id=%s AND sha256=%s",
            (account, hashlib.sha256(raw).hexdigest()),
        ).fetchone()
        assert saved and bytes(saved["raw_mime"]) == raw
        cursor = connection.execute(
            "SELECT opaque_cursor FROM sync_cursors WHERE account_id=%s", (account,)
        ).fetchone()
        assert cursor and cursor["opaque_cursor"] == "committed"
        events = connection.execute(
            "SELECT count(*) AS n FROM provider_events WHERE account_id=%s", (account,)
        ).fetchone()
        assert events and events["n"] == 2


PROTECTED_ROUTES = [
    ("GET", "/readyz", None),
    ("POST", "/v1/search", {"query": "private-canary"}),
    ("GET", f"/v1/accounts/{uuid4()}/sync-status", None),
    ("GET", f"/v1/accounts/{uuid4()}/quarantine", None),
    ("GET", f"/v1/evidence/{uuid4()}", None),
    ("GET", "/v1/proposals", None),
    (
        "POST",
        "/v1/proposals",
        {
            "payload": {"kind": "project", "name": "Synthetic"},
            "reason": "Synthetic owner request",
            "source": "unit-test",
        },
    ),
    (
        "POST",
        f"/v1/proposals/{uuid4()}/reviews",
        {"decision": "approved", "expected_version": 1},
    ),
]


@pytest.mark.parametrize(("method", "path", "body"), PROTECTED_ROUTES)
@pytest.mark.parametrize("credential_mode", ["missing", "expired", "wrong-scope"])
def test_every_content_route_denies_invalid_credentials_before_store(
    method, path, body, credential_mode
):
    store = MagicMock(spec=Store)
    credentials = registry({"email.ingest"}, expired=credential_mode == "expired")
    client = TestClient(create_app(store, credentials))
    headers = {"Idempotency-Key": str(uuid4())}
    if credential_mode != "missing":
        headers["Authorization"] = f"Bearer {TOKEN}"
    response = client.request(method, path, json=body, headers=headers)
    assert response.status_code == (403 if credential_mode == "wrong-scope" else 401)
    assert not store.mock_calls
    assert "private-canary" not in response.text


def test_forged_identity_headers_do_not_change_server_resolved_context():
    store = MagicMock(spec=Store)
    store.search.return_value = []
    credentials = registry()
    principal = credentials.authenticate(TOKEN)
    assert principal is not None
    client = TestClient(create_app(store, credentials))
    forged_tenant, forged_actor = uuid4(), uuid4()
    response = client.post(
        "/v1/search",
        json={"query": "synthetic"},
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "X-Tenant-ID": str(forged_tenant),
            "X-User-ID": str(forged_actor),
            "X-Actor-ID": str(forged_actor),
            "X-Request-ID": "attacker-controlled-canary",
        },
    )
    assert response.status_code == 200
    passed_context = store.search.call_args.args[0]
    assert passed_context.tenant_id == principal.context.tenant_id != forged_tenant
    assert passed_context.actor_id == principal.context.actor_id != forged_actor
    assert response.headers["X-Request-ID"] == str(passed_context.request_id)
    assert "attacker-controlled-canary" not in response.headers["X-Request-ID"]


@pytest.mark.parametrize("error", [NotFound("private-canary"), AccessDenied("private-canary")])
def test_store_denial_never_echoes_exception_or_private_data(error):
    store = MagicMock(spec=Store)
    store.sync_status.side_effect = error
    client = TestClient(create_app(store, registry()))
    response = client.get(
        f"/v1/accounts/{uuid4()}/sync-status", headers={"Authorization": f"Bearer {TOKEN}"}
    )
    assert response.status_code in {403, 404}
    assert "private-canary" not in response.text


def test_deep_json_is_rejected_without_store_access_or_error_echo():
    store = MagicMock(spec=Store)
    client = TestClient(create_app(store, registry()), raise_server_exceptions=False)
    response = client.post(
        "/v1/search",
        content=b"[" * 1500 + b'"private-canary"' + b"]" * 1500,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json() == {"error": "invalid_request"}
    assert not store.mock_calls


@pytest.mark.postgres
@pytest.mark.parametrize("seed_function", [seed, seed_corpus])
@pytest.mark.parametrize("account_state", ["enrolled", "not-synthetic"])
def test_demo_seeders_reject_nondemo_accounts_before_first_worker_exists(
    database, tenant, tmp_path, monkeypatch, seed_function, account_state
):
    store, administrator = database
    context, account = tenant
    with psycopg.connect(administrator) as connection:
        if account_state == "enrolled":
            connection.execute(
                "UPDATE mail_accounts SET provider_account_id='synthetic-provider-binding' "
                "WHERE id=%s",
                (account,),
            )
        else:
            connection.execute(
                "UPDATE mail_accounts SET secret_ref='vault:synthetic-test-only' WHERE id=%s",
                (account,),
            )
    (tmp_path / "demo.json").write_text(
        json.dumps(
            {
                "tenant_id": str(context.tenant_id),
                "actor_id": str(context.actor_id),
                "account_id": str(account),
            }
        )
    )
    monkeypatch.setenv("EMAIL_BRAIN_DSN", store.dsn)
    with pytest.raises((ValueError, AccessDenied)):
        if seed_function is seed:
            seed_function(tmp_path)
        else:
            seed_function(tmp_path, 5)
    with store.transaction(context) as connection:
        for table in ("provider_events", "raw_objects", "sync_cursors"):
            assert not connection.execute(
                psycopg.sql.SQL("SELECT 1 FROM {} WHERE account_id=%s").format(
                    psycopg.sql.Identifier(table)
                ),
                (account,),
            ).fetchone()


@pytest.mark.postgres
def test_corpus_enrollment_after_preflight_is_rechecked_at_ingest(
    database, tenant, tmp_path, monkeypatch
):
    store, administrator = database
    context, account = tenant
    (tmp_path / "demo.json").write_text(
        json.dumps(
            {
                "tenant_id": str(context.tenant_id),
                "actor_id": str(context.actor_id),
                "account_id": str(account),
            }
        )
    )
    monkeypatch.setenv("EMAIL_BRAIN_DSN", store.dsn)
    original_ingest = Store.ingest_page
    calls = 0

    def enroll_then_ingest(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        with psycopg.connect(administrator) as connection:
            connection.execute(
                "UPDATE mail_accounts SET provider_account_id='synthetic-binding' WHERE id=%s",
                (account,),
            )
        return original_ingest(self, *args, **kwargs)

    monkeypatch.setattr(Store, "ingest_page", enroll_then_ingest)
    with pytest.raises((ValueError, AccessDenied)):
        seed_corpus(tmp_path, 5)
    assert calls == 1  # It passed preflight but must fail inside the ingestion transaction.
    with store.transaction(context) as connection:
        assert not connection.execute("SELECT 1 FROM provider_events").fetchone()
        assert not connection.execute("SELECT 1 FROM sync_cursors").fetchone()


@pytest.mark.postgres
def test_quarantine_list_is_current_paged_and_owner_scoped(database, tenant):
    store, administrator = database
    context, account = tenant
    initial = IngestItem("q1", "p1", "v1", datetime(2026, 9, 20, tzinfo=UTC), b"")
    second = replace(initial, event_key="q2", provider_id="p2")
    store.ingest_page(context, account, None, "s1", [initial, second])
    first_page = store.quarantines(context, account, limit=1)
    assert len(first_page["results"]) == 1 and first_page["next_after"]
    second_page = store.quarantines(context, account, after=first_page["next_after"], limit=1)
    assert len(second_page["results"]) == 1 and second_page["next_after"] is None
    assert first_page["results"][0]["id"] != second_page["results"][0]["id"]
    assert first_page["raw_access"] is False and first_page["reprocessing"] is True
    assert first_page["retry_parser_version"]
    # A later bad version replaces the current receipt; repaired mail leaves this live list.
    store.ingest_page(
        context,
        account,
        "s1",
        "s2",
        [
            replace(initial, event_key="q3", version="v2"),
            replace(second, event_key="repair", raw=b"Subject: Fixed\r\n\r\nFictional repair"),
        ],
    )
    current = store.quarantines(context, account)
    assert len(current["results"]) == 1 and current["results"][0]["provider_id"] == "p1"
    assert current["results"][0]["id"] not in {
        first_page["results"][0]["id"],
        second_page["results"][0]["id"],
    }
    with store.transaction(context) as connection:
        count = connection.execute("SELECT count(*) AS n FROM quarantine_receipts").fetchone()
        assert count and count["n"] == 3  # History remains; endpoint shows only unresolved heads.
    foreign_tenant, foreign_actor = uuid4(), uuid4()
    with psycopg.connect(administrator) as connection:
        connection.execute(
            "INSERT INTO tenants(id,name) VALUES (%s,'Synthetic foreign owner')", (foreign_tenant,)
        )
        connection.execute(
            "INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES (%s,%s,'owner')",
            (foreign_tenant, foreign_actor),
        )
    credentials = registry({"email.evidence.read"})
    credentials = TokenRegistry(
        [
            credentials.credentials[0].model_copy(
                update={"tenant_id": foreign_tenant, "actor_id": foreign_actor}
            )
        ]
    )
    client = TestClient(create_app(store, credentials))
    response = client.get(
        f"/v1/accounts/{account}/quarantine",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert response.status_code == 404 and response.json() == {"error": "not_found"}
    with pytest.raises(AccessDenied):
        store.quarantines(replace(context, scopes=frozenset({"email.search"})), account)
