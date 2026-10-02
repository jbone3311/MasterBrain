"""Administrator-owned, revocable OIDC source grants for the Brain read path."""

from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

import psycopg
import pytest
import test_oidc as oidc
import test_oidc_postgres as oidc_pg
import test_postgres as pg
from cross_source_preview import build_preview
from fastapi.testclient import TestClient

from email_brain.api import create_app
from email_brain.domain.models import ExternalIdentity
from email_brain.oidc import OIDCAuthenticator
from email_brain.store import AccessDenied

pytestmark = pytest.mark.postgres
database = pg.database
keys = oidc.keys
identity_admin_login = oidc_pg.identity_admin_login
READ_SCOPES = [
    "brain.search", "knowledge.search", "brain.evidence.read", "brain.content.read",
    "brain.changes.read",
]


@pytest.fixture
def preview(database, tmp_path):
    store, admin = database
    return build_preview(store, admin, tmp_path)


@pytest.fixture
def assistant(preview, database, keys):
    store, admin = database
    fake = oidc.FakeIssuer(keys[0], oidc.config("rfc9068"))
    binding = uuid4()
    subject = "fictional-brain-" + binding.hex
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO external_identities(id,tenant_id,actor_id,issuer,subject,client_id,"
            "scopes,client_kind) VALUES (%s,%s,%s,%s,%s,%s,%s,'assistant')",
            (
                binding, preview.context.tenant_id, preview.context.actor_id,
                fake.config.issuer, subject, oidc.CLIENT, READ_SCOPES,
            ),
        )
    raw = oidc.token(keys[0], fake.config, payload=oidc.claims(fake.config, sub=subject))
    auth = OIDCAuthenticator(store, fake.verifier())
    return binding, raw, auth


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": "Bearer " + token}


def test_oidc_brain_assistant_requires_enrollment_and_revokes_every_read(
    preview, database, assistant, identity_admin_login
) -> None:
    store, admin = database
    binding, raw, auth = assistant
    dsn, admin_role = identity_admin_login
    with psycopg.connect(admin) as conn:
        assert conn.execute(
            "SELECT id FROM public.resolve_external_identity(%s,%s,%s)",
            (auth.verifier.config.issuer, "fictional-brain-" + binding.hex, oidc.CLIENT),
        ).fetchone() is None
    assert auth.authenticate(raw) is None
    verified = auth.verifier.verify(raw)
    assert verified is not None
    forged = replace(
        preview.context,
        scopes=frozenset(READ_SCOPES),
        identity=ExternalIdentity(
            binding,verified.issuer,verified.subject,verified.client_id,
            1,"assistant",verified.expires_at,
        ),
    )
    with pytest.raises(AccessDenied), store.transaction(forged):
        pass
    with TestClient(create_app(store, auth), base_url="http://127.0.0.1") as client:
        assert client.post(
            "/v1/brain/current-search", json={"query": "insurance"},
            headers=_headers(raw),
        ).status_code == 401

    with TestClient(preview.app, base_url="http://127.0.0.1") as owner:
        original = owner.post(
            "/v1/brain/current-search", json={"query": "insurance"},
            headers=_headers(preview.token),
        ).json()
    file_hit = original["layers"]["fileos"][0]
    email_hit = original["layers"]["email_messages"][0]
    assert file_hit["source_id"] != email_hit["source_id"]
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "INSERT INTO external_identity_sources(tenant_id,binding_id,source_id) "
            "VALUES (%s,%s,%s)",
            (preview.context.tenant_id, binding, file_hit["source_id"]),
        )
    with store.transaction(replace(
        forged,
        identity=replace(forged.identity, revision=2),
        source_ids=frozenset({file_hit["source_id"]}),
    )):
        pass
    principal = auth.authenticate(raw)
    assert principal and principal.context.source_ids == frozenset({file_hit["source_id"]})
    assert principal.context.identity.revision == 2
    with TestClient(create_app(store, auth), base_url="http://127.0.0.1") as client:
        response = client.post(
            "/v1/brain/current-search", json={"query": "insurance"},
            headers=_headers(raw),
        )
        assert response.status_code == 200
        assert response.json()["layers"]["fileos"] == original["layers"]["fileos"]
        assert response.json()["layers"]["email_messages"] == []
        assert email_hit["source_id"] not in response.text
        coverage = client.get("/v1/brain/current-coverage", headers=_headers(raw))
        assert coverage.status_code == 200
        assert [row["source_id"] for row in coverage.json()["results"]] == [
            file_hit["source_id"]
        ]
        assert client.get(
            f"/v1/brain/current-coverage?after={email_hit['source_id']}",
            headers=_headers(raw),
        ).status_code == 404
        changes = client.get("/v1/brain/changes", headers=_headers(raw))
        assert changes.status_code == 200
        assert all(
            row["source_id"] == file_hit["source_id"]
            for row in changes.json()["results"]
        )
        assert client.get(
            f"/v1/brain/evidence/{file_hit['evidence_id']}", headers=_headers(raw)
        ).status_code == 200
        assert client.get(
            f"/v1/brain/evidence/{email_hit['evidence_id']}", headers=_headers(raw)
        ).status_code == 404
        assert client.post(
            f"/v1/brain/evidence/{email_hit['evidence_id']}/content",
            json={"max_chars": 100}, headers=_headers(raw),
        ).status_code == 404
        assert client.post(
            "/v1/knowledge/search", json={"query": "insurance"},
            headers=_headers(raw),
        ).status_code == 403

    with pytest.raises(AccessDenied), store.transaction(
        replace(principal.context, source_ids=frozenset({email_hit["source_id"]}))
    ):
        pass
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "DELETE FROM external_identity_sources "
            "WHERE tenant_id=%s AND binding_id=%s AND source_id=%s",
            (preview.context.tenant_id, binding, file_hit["source_id"]),
        )
    with pytest.raises(AccessDenied), store.transaction(principal.context):
        pass
    assert auth.authenticate(raw) is None
    with TestClient(create_app(store, auth), base_url="http://127.0.0.1") as client:
        assert client.get(
            f"/v1/brain/evidence/{file_hit['evidence_id']}", headers=_headers(raw)
        ).status_code == 401
    with psycopg.connect(admin) as conn:
        events = conn.execute(
            "SELECT event_type,metadata->>'database_role',metadata->>'source_id' "
            "FROM audit_events WHERE resource_id=%s AND "
            "event_type IN ('source_grant.insert','source_grant.delete') "
            "ORDER BY occurred_at,id",
            (str(binding),),
        ).fetchall()
        assert events == [
            ("source_grant.insert", admin_role, file_hit["source_id"]),
            ("source_grant.delete", admin_role, file_hit["source_id"]),
        ]


def test_oidc_source_grants_are_tenant_bound_and_admin_only(
    preview, database, assistant, identity_admin_login
) -> None:
    store, admin = database
    binding, raw, auth = assistant
    dsn, _ = identity_admin_login
    foreign_tenant = uuid4()
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO tenants(id,name) VALUES (%s,'Other synthetic tenant')",
            (foreign_tenant,),
        )
        conn.execute(
            "INSERT INTO brain_sources(tenant_id,id,kind,display_name) "
            "VALUES (%s,'foreign_only','email','Foreign synthetic source')",
            (foreign_tenant,),
        )
    for source_id in ("foreign_only", "not_registered"):
        with pytest.raises(psycopg.errors.ForeignKeyViolation), psycopg.connect(dsn) as conn:
            conn.execute(
                "INSERT INTO external_identity_sources(tenant_id,binding_id,source_id) "
                "VALUES (%s,%s,%s)",
                (preview.context.tenant_id, binding, source_id),
            )
    with pytest.raises(psycopg.errors.InsufficientPrivilege), store.transaction(
        preview.context
    ) as conn:
        conn.execute("SELECT * FROM external_identity_sources")
    with pytest.raises(psycopg.errors.InsufficientPrivilege), store.transaction(
        preview.context
    ) as conn:
        conn.execute(
            "INSERT INTO external_identity_sources(tenant_id,binding_id,source_id) "
            "VALUES (%s,%s,'trial_files')",
            (preview.context.tenant_id, binding),
        )
    assert auth.authenticate(raw) is None
    with pytest.raises(psycopg.errors.CheckViolation), psycopg.connect(admin) as conn:
        conn.execute(
            "UPDATE external_identities SET scopes=%s WHERE id=%s",
            (READ_SCOPES + ["email.search"], binding),
        )


def test_oidc_partial_revocation_preserves_only_remaining_source(
    preview, database, assistant, identity_admin_login
) -> None:
    store, admin = database
    binding, raw, auth = assistant
    dsn, _ = identity_admin_login
    with TestClient(preview.app, base_url="http://127.0.0.1") as owner:
        original = owner.post(
            "/v1/brain/current-search", json={"query": "insurance"},
            headers=_headers(preview.token),
        ).json()
    file_hit = original["layers"]["fileos"][0]
    email_hit = original["layers"]["email_messages"][0]
    with psycopg.connect(dsn) as conn:
        for source_id in (file_hit["source_id"], email_hit["source_id"]):
            conn.execute(
                "INSERT INTO external_identity_sources(tenant_id,binding_id,source_id) "
                "VALUES (%s,%s,%s)",
                (preview.context.tenant_id, binding, source_id),
            )
    old = auth.authenticate(raw)
    assert old and old.context.source_ids == frozenset({
        file_hit["source_id"], email_hit["source_id"]
    })
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "DELETE FROM external_identity_sources "
            "WHERE tenant_id=%s AND binding_id=%s AND source_id=%s",
            (preview.context.tenant_id, binding, email_hit["source_id"]),
        )
    with pytest.raises(AccessDenied), store.transaction(old.context):
        pass
    current = auth.authenticate(raw)
    assert current and current.context.source_ids == frozenset({file_hit["source_id"]})
    with TestClient(create_app(store, auth), base_url="http://127.0.0.1") as client:
        response = client.post(
            "/v1/brain/current-search", json={"query": "insurance"},
            headers=_headers(raw),
        )
        assert response.status_code == 200
        assert response.json()["layers"]["fileos"] == original["layers"]["fileos"]
        assert response.json()["layers"]["email_messages"] == []
        assert client.get(
            f"/v1/brain/evidence/{email_hit['evidence_id']}", headers=_headers(raw)
        ).status_code == 404
        assert client.post(
            f"/v1/brain/evidence/{email_hit['evidence_id']}/content",
            json={"max_chars": 100}, headers=_headers(raw),
        ).status_code == 404
    with psycopg.connect(admin) as conn:
        assert conn.execute(
            "SELECT revision FROM external_identities WHERE id=%s", (binding,)
        ).fetchone() == (4,)


def test_oidc_source_grant_cap_and_binding_revision(preview, database, assistant) -> None:
    _, admin = database
    binding, raw, auth = assistant
    with psycopg.connect(admin) as conn:
        for number in range(21):
            conn.execute(
                "INSERT INTO brain_sources(tenant_id,id,kind,display_name) "
                "VALUES (%s,%s,'email','Synthetic cap source')",
                (preview.context.tenant_id, f"cap_{number}"),
            )
        for number in range(20):
            conn.execute(
                "INSERT INTO external_identity_sources(tenant_id,binding_id,source_id) "
                "VALUES (%s,%s,%s)",
                (preview.context.tenant_id, binding, f"cap_{number}"),
            )
    principal = auth.authenticate(raw)
    assert principal and len(principal.context.source_ids) == 20
    assert principal.context.identity.revision == 21
    with pytest.raises(psycopg.errors.RaiseException), psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO external_identity_sources(tenant_id,binding_id,source_id) "
            "VALUES (%s,%s,'cap_20')",
            (preview.context.tenant_id, binding),
        )
    with psycopg.connect(admin) as conn:
        assert conn.execute(
            "SELECT count(*) FROM external_identity_sources WHERE binding_id=%s",
            (binding,),
        ).fetchone() == (20,)


def test_oidc_status_only_assistant_still_requires_source_grant(
    preview, database, assistant, identity_admin_login
) -> None:
    store, admin = database
    binding, raw, auth = assistant
    dsn, _ = identity_admin_login
    with psycopg.connect(admin) as conn:
        conn.execute(
            "UPDATE external_identities SET scopes=ARRAY['brain.changes.read']::text[] "
            "WHERE id=%s",
            (binding,),
        )
    assert auth.authenticate(raw) is None
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "INSERT INTO external_identity_sources(tenant_id,binding_id,source_id) "
            "VALUES (%s,%s,'trial_files')",
            (preview.context.tenant_id, binding),
        )
    with psycopg.connect(admin) as conn:
        assert conn.execute(
            "SELECT id FROM public.resolve_external_identity(%s,%s,%s)",
            (auth.verifier.config.issuer, "fictional-brain-" + binding.hex, oidc.CLIENT),
        ).fetchone() is None
    principal = auth.authenticate(raw)
    assert principal and principal.context.scopes == frozenset({"brain.changes.read"})
    with TestClient(create_app(store, auth), base_url="http://127.0.0.1") as client:
        headers = _headers(raw)
        coverage = client.get("/v1/brain/current-coverage", headers=headers)
        assert coverage.status_code == 200
        assert [row["source_id"] for row in coverage.json()["results"]] == [
            "trial_files"
        ]
        assert client.get("/v1/brain/changes", headers=headers).status_code == 200
        assert client.post(
            "/v1/brain/current-search", json={"query": "insurance"}, headers=headers
        ).status_code == 403
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "DELETE FROM external_identity_sources WHERE tenant_id=%s AND binding_id=%s",
            (preview.context.tenant_id, binding),
        )
    with pytest.raises(AccessDenied), store.transaction(principal.context):
        pass
    assert auth.authenticate(raw) is None
