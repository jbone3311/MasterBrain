"""Fake code exchange, genuine signature validation and real SQL session authority."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
import test_browser_auth as browser_tests
import test_oidc_postgres as identity_tests
import test_postgres as pg

from email_brain.schemas import SearchRequest

pytestmark = pytest.mark.postgres
database, tenant, keys, setup = (
    identity_tests.database,
    identity_tests.tenant,
    identity_tests.keys,
    identity_tests.setup,
)


def browser(setup):
    store, _, _, _, fake, _, raw, auth = setup
    fixture = browser_tests.Fixture(fake.key, fake.config.profile, real_auth=auth, raw=raw)
    assert fixture.store is store
    client = fixture.client()
    browser_tests.web_login(client)
    session = client.get("/auth/session").json()
    headers = {"Origin": fixture.config.public_origin, "X-CSRF-Token": session["csrf_token"]}
    return fixture, client, headers


@pytest.mark.parametrize("setup", ["rfc9068", "entra-v2"], indirect=True)
def test_browser_search_isolation_and_logout(setup, database):
    store, _, ctx, account, _, _, _, _ = setup
    store.ingest_page(ctx, account, None, "own", [pg.item()])
    other, other_account = pg.tenant.__wrapped__(database)
    store.ingest_page(other, other_account, None, "other", [pg.item()])
    evidence = store.search(other, SearchRequest(query="Melron"))[0]["evidence_id"]
    _, client, headers = browser(setup)
    response = client.post("/v1/search", headers=headers, json={"query": "Melron"})
    assert response.status_code == 200 and len(response.json()["results"]) == 1
    assert client.get(f"/v1/evidence/{evidence}").status_code == 404
    assert client.post("/auth/logout", headers=headers).status_code == 204
    assert client.post("/v1/search", headers=headers, json={"query": "Melron"}).status_code == 401


@pytest.mark.parametrize(
    "change", ["active", "scopes", "kind", "membership", "reenabled", "delete"]
)
def test_current_database_authority_invalidates_browser_session(setup, change):
    _, admin, ctx, _, _, binding, _, _ = setup
    _, client, headers = browser(setup)
    with psycopg.connect(admin) as conn:
        if change == "active":
            conn.execute("UPDATE external_identities SET active=false WHERE id=%s", (binding,))
        elif change == "scopes":
            conn.execute(
                "UPDATE external_identities SET scopes=ARRAY['email.search'] WHERE id=%s",
                (binding,),
            )
        elif change == "kind":
            conn.execute(
                "UPDATE external_identities SET client_kind='assistant',"
                "scopes=ARRAY['email.search'] WHERE id=%s",
                (binding,),
            )
        elif change == "membership":
            conn.execute(
                "UPDATE tenant_memberships SET role='member' WHERE tenant_id=%s", (ctx.tenant_id,)
            )
        elif change == "reenabled":
            conn.execute("UPDATE external_identities SET active=false WHERE id=%s", (binding,))
            conn.execute("UPDATE external_identities SET active=true WHERE id=%s", (binding,))
        else:
            conn.execute("DELETE FROM external_identities WHERE id=%s", (binding,))
    assert client.post("/v1/search", headers=headers, json={"query": "Melron"}).status_code == 401
    assert not client.get("/auth/session").json()["authenticated"]


def test_database_clock_rejects_expired_saved_identity(setup):
    fixture, client, headers = browser(setup)
    key, row = next(iter(fixture.browser._sessions.items()))
    old = row.principal.context
    expired = replace(old.identity, expires_at=datetime.now(UTC) - timedelta(seconds=1))
    fixture.browser._sessions[key] = replace(
        row, principal=replace(row.principal, context=replace(old, identity=expired))
    )
    assert client.post("/v1/search", headers=headers, json={"query": "Melron"}).status_code == 401


def test_unknown_subject_cannot_create_mapping_or_session(setup):
    _, admin, _, _, fake, binding, raw, auth = setup
    with psycopg.connect(admin) as conn:
        conn.execute("DELETE FROM external_identities WHERE id=%s", (binding,))
    fixture = browser_tests.Fixture(fake.key, real_auth=auth, raw=raw)
    client = fixture.client()
    state = browser_tests.web_start(client)
    assert (
        client.get(
            "/auth/callback",
            params={
                "state": state,
                "code": "fictional-code",
            },
        ).status_code
        == 401
    )
    assert not fixture.browser._sessions
    with psycopg.connect(admin) as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM external_identities WHERE id=%s", (binding,)
            ).fetchone()[0]
            == 0
        )
