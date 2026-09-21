"""Verified-token -> real SQL/API authority, including stale saved contexts."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
import test_oidc as oidc
import test_postgres as pg
from fastapi.testclient import TestClient
from psycopg import sql

from email_brain.api import create_app
from email_brain.auth import AuthenticationUnavailable
from email_brain.oidc import OIDCAuthenticator
from email_brain.schemas import SearchRequest
from email_brain.store import AccessDenied, Store

pytestmark = pytest.mark.postgres
database, tenant, keys = pg.database, pg.tenant, oidc.keys
SCOPES = [
    "email.search",
    "email.evidence.read",
    "email.proposal.create",
    "email.proposal.read",
    "email.review",
]


@pytest.fixture
def setup(database, tenant, keys, request):
    store, admin = database
    ctx, account = tenant
    fake = oidc.FakeIssuer(keys[0], oidc.config(getattr(request, "param", "rfc9068")))
    subject = "fictional-" + uuid4().hex
    binding = uuid4()
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO external_identities(id,tenant_id,actor_id,issuer,subject,client_id,"
            "scopes,client_kind) VALUES (%s,%s,%s,%s,%s,%s,%s,'human')",
            (
                binding,
                ctx.tenant_id,
                ctx.actor_id,
                fake.config.issuer,
                subject,
                oidc.CLIENT,
                SCOPES,
            ),
        )
    raw = oidc.token(keys[0], fake.config, payload=oidc.claims(fake.config, sub=subject))
    auth = OIDCAuthenticator(store, fake.verifier())
    return store, admin, ctx, account, fake, binding, raw, auth


@pytest.mark.parametrize("setup", ["rfc9068", "entra-v2"], indirect=True)
def test_verified_mapping_api_search_and_no_inferred_tenant(setup):
    store, _, ctx, account, fake, binding, raw, auth = setup
    store.ingest_page(ctx, account, None, "c1", [pg.item()])
    principal = auth.authenticate(raw)
    assert principal and principal.context.tenant_id == ctx.tenant_id
    assert principal.context.identity.binding_id == binding
    assert principal.context.scopes == frozenset(SCOPES)
    client = TestClient(create_app(store, auth))
    headers = {"Authorization": "Bearer " + raw}
    assert client.get("/readyz", headers=headers).status_code == 200
    response = client.post("/v1/search", json={"query": "Melron"}, headers=headers)
    assert response.status_code == 200 and "Melron" in response.text
    forged = oidc.token(
        fake.key,
        fake.config,
        payload=oidc.claims(
            fake.config,
            sub=principal.context.identity.subject,
            tenant_id=str(uuid4()),
            scopes=["email.ingest"],
            roles=["administrator"],
        ),
    )
    assert auth.authenticate(forged).context.tenant_id == ctx.tenant_id
    assert "email.ingest" not in auth.authenticate(forged).context.scopes
    assert (
        client.post(
            "/v1/search", json={"query": "Melron", "tenant_id": str(uuid4())}, headers=headers
        ).status_code
        == 422
    )


def test_unknown_identity_never_enrolls(setup):
    store, admin, _, _, fake, _, _, auth = setup
    with psycopg.connect(admin) as conn:
        before = conn.execute("SELECT count(*) FROM external_identities").fetchone()[0]
    raw = oidc.token(fake.key, fake.config, payload=oidc.claims(fake.config, sub="unknown"))
    client = TestClient(create_app(store, auth))
    assert client.get("/readyz", headers={"Authorization": "Bearer " + raw}).status_code == 401
    with psycopg.connect(admin) as conn:
        assert conn.execute("SELECT count(*) FROM external_identities").fetchone()[0] == before


@pytest.mark.parametrize("change", ["active", "scopes", "kind", "membership", "delete"])
def test_revocation_invalidates_saved_context_and_new_api(setup, change):
    store, admin, ctx, _, _, binding, raw, auth = setup
    principal = auth.authenticate(raw)
    assert principal
    with psycopg.connect(admin) as conn:
        if change == "active":
            conn.execute("UPDATE external_identities SET active=false WHERE id=%s", (binding,))
        elif change == "scopes":
            conn.execute(
                "UPDATE external_identities SET scopes=ARRAY['email.evidence.read'] WHERE id=%s",
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
        else:
            conn.execute("DELETE FROM external_identities WHERE id=%s", (binding,))
    with pytest.raises(AccessDenied), store.transaction(principal.context):
        pass
    fresh = auth.authenticate(raw)
    if change in {"active", "membership", "delete"}:
        assert fresh is None
    else:
        assert fresh and fresh.context.identity.revision == 2
        assert "email.review" not in fresh.context.scopes


def test_disabled_reenabled_binding_cannot_resurrect_old_context(setup):
    store, admin, _, _, _, binding, raw, auth = setup
    previous = auth.authenticate(raw)
    with psycopg.connect(admin) as conn:
        conn.execute("UPDATE external_identities SET active=false WHERE id=%s", (binding,))
        conn.execute("UPDATE external_identities SET active=true WHERE id=%s", (binding,))
    assert auth.authenticate(raw).context.identity.revision == 3
    with pytest.raises(AccessDenied), store.transaction(previous.context):
        pass


def test_expired_or_broadened_context_fails_before_data(setup):
    store, _, _, _, _, _, raw, auth = setup
    ctx = auth.authenticate(raw).context
    expired = replace(ctx.identity, expires_at=datetime.now(UTC) - timedelta(seconds=1))
    for stale in (
        replace(ctx, identity=expired),
        replace(ctx, tenant_id=uuid4()),
        replace(ctx, actor_id=uuid4()),
        replace(ctx, scopes=ctx.scopes | {"email.ingest"}),
    ):
        with pytest.raises(AccessDenied), store.transaction(stale):
            pass


def test_current_mapping_still_denies_other_tenant_evidence(setup, database):
    store, _, _, _, _, _, raw, auth = setup
    foreign_ctx, foreign_account = pg.tenant.__wrapped__(database)
    store.ingest_page(foreign_ctx, foreign_account, None, "foreign", [pg.item()])
    evidence = store.search(foreign_ctx, SearchRequest(query="Melron"))[0]["evidence_id"]
    client = TestClient(create_app(store, auth))
    headers = {"Authorization": "Bearer " + raw}
    assert client.get(f"/v1/evidence/{evidence}", headers=headers).status_code == 404
    assert store.search(auth.authenticate(raw).context, SearchRequest(query="Melron")) == []


def test_identity_rls_without_verified_context_and_exact_lookup(setup):
    store, _, ctx, _, fake, binding, raw, auth = setup
    verified = auth.verifier.verify(raw)
    with store.transaction(ctx) as conn:
        assert conn.execute("SELECT * FROM external_identities").fetchall() == []
    with store.connection() as conn:
        assert conn.execute("SELECT * FROM external_identities").fetchall() == []
        store.identity_context(conn, fake.config.issuer, verified.subject, oidc.CLIENT)
        assert [row["id"] for row in conn.execute("SELECT * FROM external_identities")] == [binding]
        store.identity_context(conn, fake.config.issuer, verified.subject, "different-client")
        assert conn.execute("SELECT * FROM external_identities").fetchall() == []
    # Transaction-local settings cannot survive into a subsequent connection.
    with store.connection() as conn:
        assert conn.execute("SELECT * FROM external_identities").fetchall() == []


@pytest.mark.parametrize("operation", ["INSERT", "UPDATE", "DELETE"])
def test_runtime_cannot_manage_identity_bindings(setup, operation):
    store, _, _, _, _, binding, raw, auth = setup
    ctx = auth.authenticate(raw).context
    command = {
        "INSERT": "INSERT INTO external_identities SELECT * FROM external_identities",
        "UPDATE": "UPDATE external_identities SET active=false",
        "DELETE": "DELETE FROM external_identities",
    }[operation]
    with pytest.raises(psycopg.errors.InsufficientPrivilege), store.transaction(ctx) as conn:
        conn.execute(command)
    assert auth.authenticate(raw).context.identity.binding_id == binding


@pytest.mark.parametrize(
    "column,value",
    [
        ("subject", "changed"),
        ("issuer", "https://other.example.invalid"),
        ("client_id", "other"),
        ("id", uuid4()),
        ("tenant_id", uuid4()),
        ("actor_id", uuid4()),
        ("revision", 7),
        ("created_at", datetime.now(UTC)),
    ],
)
def test_binding_identity_immutable(setup, column, value):
    _, admin, _, _, _, binding, _, _ = setup
    with pytest.raises(psycopg.errors.RaiseException), psycopg.connect(admin) as conn:
        conn.execute(
            sql.SQL("UPDATE external_identities SET {}=%s WHERE id=%s").format(
                sql.Identifier(column)
            ),
            (value, binding),
        )


@pytest.mark.parametrize(
    "scopes,kind",
    [
        ([], "human"),
        ([None], "human"),
        (["email.ingest"], "human"),
        (["email.process"], "human"),
        (["email.document.process"], "human"),
        (["email.review"], "assistant"),
        (["email.search"], "worker"),
        (["email.search", "email.search"], "human"),
    ],
)
def test_sql_scope_kind_constraints(setup, scopes, kind):
    _, admin, _, _, _, binding, _, _ = setup
    with pytest.raises(psycopg.Error), psycopg.connect(admin) as conn:
        conn.execute(
            "UPDATE external_identities SET scopes=%s,client_kind=%s WHERE id=%s",
            (scopes, kind, binding),
        )


def test_assistant_cannot_review_even_with_signed_owner_claim(setup):
    store, admin, _, _, fake, binding, raw, auth = setup
    with psycopg.connect(admin) as conn:
        conn.execute(
            "UPDATE external_identities SET client_kind='assistant',"
            "scopes=ARRAY['email.search','email.proposal.create'] WHERE id=%s",
            (binding,),
        )
    verified = auth.verifier.verify(raw)
    malicious = oidc.token(
        fake.key,
        fake.config,
        payload=oidc.claims(
            fake.config,
            sub=verified.subject,
            roles=["owner"],
            client_kind="human",
            scope="email.access email.review",
        ),
    )
    client = TestClient(create_app(store, auth))
    response = client.post(
        f"/v1/proposals/{uuid4()}/reviews",
        json={"decision": "approved", "expected_version": 1},
        headers={"Authorization": "Bearer " + malicious},
    )
    assert response.status_code == 403


def test_database_outage_and_unsafe_role_fail_closed(setup, monkeypatch):
    store, admin, _, _, fake, _, raw, auth = setup
    assert OIDCAuthenticator(Store(admin), fake.verifier()).authenticate(raw) is None

    def unavailable():
        raise psycopg.OperationalError("sensitive SQL diagnostics")

    monkeypatch.setattr(store, "connection", unavailable)
    with pytest.raises(AuthenticationUnavailable) as exc:
        auth.authenticate(raw)
    assert str(exc.value) == ""


def test_admin_binding_changes_are_audited_without_subject(setup):
    _, admin, _, _, _, binding, raw, auth = setup
    subject = auth.verifier.verify(raw).subject
    with psycopg.connect(admin) as conn:
        conn.execute("UPDATE external_identities SET active=false WHERE id=%s", (binding,))
        conn.execute("DELETE FROM external_identities WHERE id=%s", (binding,))
        rows = conn.execute(
            "SELECT event_type,actor_id,metadata FROM audit_events "
            "WHERE resource_id=%s ORDER BY occurred_at,id",
            (str(binding),),
        ).fetchall()
    assert sorted(row[0] for row in rows) == [
        "identity.delete",
        "identity.insert",
        "identity.update",
    ]
    assert all(row[1] is None and "database_role" in row[2] for row in rows)
    assert subject not in repr(rows) and raw not in repr(rows)


def test_mapping_unique_per_verified_triple(setup):
    _, admin, ctx, _, fake, _, raw, auth = setup
    subject = auth.verifier.verify(raw).subject
    with pytest.raises(psycopg.errors.UniqueViolation), psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO external_identities(id,tenant_id,actor_id,issuer,subject,client_id,"
            "scopes,client_kind) VALUES (%s,%s,%s,%s,%s,%s,%s,'human')",
            (
                uuid4(),
                ctx.tenant_id,
                ctx.actor_id,
                fake.config.issuer,
                subject,
                oidc.CLIENT,
                SCOPES,
            ),
        )
