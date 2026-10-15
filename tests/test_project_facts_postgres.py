"""Fictional PostgreSQL proof of quoted project-fact publication and paging."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
import test_postgres as pg
from fastapi.testclient import TestClient

from email_brain.api import create_app
from email_brain.auth import Credential, TokenRegistry
from email_brain.store import Conflict, NotFound, Store
from masterbrain.knowledge import KnowledgeCore
from masterbrain.knowledge_schema import (
    ProjectDossierRequest,
    ProjectFactPageRequest,
    ProjectFactWrite,
    ProjectWrite,
)
from masterbrain.project_facts import ProjectFacts

pytestmark = pytest.mark.postgres
database, tenant = pg.database, pg.tenant
QUOTE = "Fictional Melron deal briefing"
NOW = datetime(2026, 10, 14, tzinfo=UTC)


def _source(store: Store, ctx: pg.TenantContext, account, key: str, cursor: str | None) -> str:
    store.ingest_page(ctx, account, cursor, key, [
        replace(pg.item(key, body=QUOTE), provider_id=key),
    ])
    with store.transaction(ctx) as conn:
        legacy_id = conn.execute(
            "SELECT v.id FROM message_versions v JOIN messages m "
            "ON m.tenant_id=v.tenant_id AND m.id=v.message_id "
            "WHERE m.provider_message_id=%s ORDER BY v.id DESC LIMIT 1",
            (key,),
        ).fetchone()["id"]
    return pg.DataCoreStore(store).bridge_current_email_version(
        ctx, legacy_id, uuid4(), code_revision="project-fact-fictional-v1",
    ).evidence_id


def _prepared(store: Store, tenant_data: tuple) -> tuple:
    raw_ctx, account = tenant_data
    ctx = replace(
        pg.datacore_context(raw_ctx),
        scopes=pg.datacore_context(raw_ctx).scopes | frozenset({
            "knowledge.review", "knowledge.search", "brain.content.read",
        }),
    )
    evidence_id = _source(store, ctx, account, "fictional-fact-message-1", None)
    project = KnowledgeCore(store).publish(ctx, ProjectWrite(
        kind="project", title="Fictional Melron deal", state="active",
        evidence_ids=[evidence_id], source_quote=QUOTE,
        confidence=1.0, observed_at=NOW, reviewed=True,
    ), uuid4())
    return ctx, account, project.object_id, evidence_id


def _body(project_id: str, evidence_id: str, *, quote: str = QUOTE,
          value: str = "One hundred fictional units",
          supersedes_id: str | None = None) -> ProjectFactWrite:
    return ProjectFactWrite(
        kind="project_fact", project_id=project_id, predicate="capital.amount",
        value=value, value_type="text", evidence_ids=[evidence_id],
        quote_evidence_id=evidence_id, source_quote=quote,
        confidence=1.0, observed_at=NOW, reviewed=True,
        supersedes_id=supersedes_id,
    )


def test_project_fact_schema_rejects_invalid_source_text():
    project_id = "project_" + "1" * 32
    evidence_id = "evidence_" + "2" * 32
    with pytest.raises(ValueError):
        _body(project_id, evidence_id, value="invalid\x00value")
    with pytest.raises(ValueError):
        _body(project_id, evidence_id, quote="invalid\ud800quote")


def test_project_fact_exact_quote_replay_and_visible_successor(database, tenant):
    store, _ = database
    ctx, _, project_id, evidence_id = _prepared(store, tenant)
    facts = ProjectFacts(store)
    with pytest.raises(ValueError, match="quote lacks"):
        facts.publish(ctx, project_id, _body(project_id, evidence_id, quote="invented"), uuid4())
    key = uuid4()
    first = facts.publish(ctx, project_id, _body(project_id, evidence_id), key)
    assert first["changed"] and first["reviewed"]
    assert facts.publish(ctx, project_id, _body(project_id, evidence_id), key) == {
        **first, "changed": False,
    }
    with pytest.raises(Conflict):
        facts.publish(ctx, project_id, _body(project_id, evidence_id, value="different"), key)
    page = facts.page(ctx, project_id, ProjectFactPageRequest())
    assert [row["object_id"] for row in page["results"]] == [first["object_id"]]
    assert page["results"][0]["derivation"] == "source_stated"
    assert page["results"][0]["quote_evidence_id"] == evidence_id
    assert "source_quote" not in page["results"][0]
    successor = facts.publish(
        ctx, project_id,
        _body(project_id, evidence_id, value="Two hundred fictional units",
              supersedes_id=first["object_id"]), uuid4(),
    )
    assert [row["object_id"] for row in facts.page(
        ctx, project_id, ProjectFactPageRequest(),
    )["results"]] == [successor["object_id"]]
    assert {row["object_id"] for row in facts.page(
        ctx, project_id, ProjectFactPageRequest(visibility="retained"),
    )["results"]} == {first["object_id"], successor["object_id"]}
    dossier = KnowledgeCore(store).project_dossier(
        ctx, project_id, ProjectDossierRequest(fact_limit=1),
    )
    assert [row["object_id"] for row in dossier["facts"]] == [successor["object_id"]]
    assert dossier["facts_truncated"] is False
    retained_dossier = KnowledgeCore(store).project_dossier(
        ctx, project_id, ProjectDossierRequest(fact_limit=1, visibility="retained"),
    )
    assert retained_dossier["facts_truncated"] is True


def test_project_fact_other_tenant_and_wrong_project_denied(database, tenant):
    store, _ = database
    ctx, _, project_id, evidence_id = _prepared(store, tenant)
    facts = ProjectFacts(store)
    facts.publish(ctx, project_id, _body(project_id, evidence_id), uuid4())
    with pytest.raises(ValueError, match="subject mismatch"):
        facts.publish(ctx, project_id, _body("project_" + "0" * 32, evidence_id), uuid4())
    foreign_ctx, _ = pg.tenant.__wrapped__(database)
    foreign_ctx = replace(foreign_ctx, scopes=ctx.scopes)
    with pytest.raises(NotFound):
        facts.page(foreign_ctx, project_id, ProjectFactPageRequest())
    with pytest.raises(NotFound):
        facts.publish(foreign_ctx, project_id, _body(project_id, evidence_id), uuid4())


def test_project_fact_grants_exclusion_and_hidden_before_limit(database, tenant):
    store, admin = database
    ctx, _, project_id, visible_evidence = _prepared(store, tenant)
    second_account = uuid4()
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO mail_accounts(id,tenant_id,provider,address,secret_ref) "
            "VALUES (%s,%s,'fastmail','fact-other@example.invalid','synthetic:none')",
            (second_account, ctx.tenant_id),
        )
    hidden_evidence = _source(
        store, ctx, second_account, "fictional-hidden-fact-message", None,
    )
    with store.transaction(ctx) as conn:
        visible_source = conn.execute(
            "SELECT v.source_id FROM brain_evidence e JOIN brain_source_versions v "
            "ON v.tenant_id=e.tenant_id AND v.id=e.source_version_id WHERE e.id=%s",
            (visible_evidence,),
        ).fetchone()["source_id"]
    scoped = replace(ctx, source_ids=frozenset({visible_source}))
    facts = ProjectFacts(store)
    visible = facts.publish(
        ctx, project_id, _body(project_id, visible_evidence), uuid4(),
    )
    with pytest.raises(NotFound):
        facts.publish(scoped, project_id, _body(project_id, hidden_evidence), uuid4())
    for index in range(30):
        facts.publish(
            ctx, project_id,
            _body(project_id, hidden_evidence, value=f"Hidden fictional value {index}"),
            uuid4(),
        )
    restricted_page = facts.page(scoped, project_id, ProjectFactPageRequest(limit=1))
    assert [row["object_id"] for row in restricted_page["results"]] == [
        visible["object_id"],
    ]
    assert restricted_page["next_cursor"] is None
    restricted_dossier = KnowledgeCore(store).project_dossier(
        scoped, project_id, ProjectDossierRequest(fact_limit=1),
    )
    assert [row["object_id"] for row in restricted_dossier["facts"]] == [
        visible["object_id"],
    ]
    assert restricted_dossier["facts_truncated"] is False
    unrestricted = facts.page(ctx, project_id, ProjectFactPageRequest(limit=1))
    assert unrestricted["next_cursor"] is not None
    with pytest.raises(NotFound):
        facts.page(scoped, project_id, ProjectFactPageRequest(
            limit=1, recorded_cutoff_at=unrestricted["recorded_cutoff_at"],
            after=unrestricted["next_cursor"],
        ))
    with psycopg.connect(admin) as conn:
        conn.execute(
            "UPDATE message_sync_state SET status='excluded' "
            "WHERE tenant_id=%s AND provider_id='fictional-hidden-fact-message'",
            (ctx.tenant_id,),
        )
    after_exclusion = facts.page(ctx, project_id, ProjectFactPageRequest(limit=1))
    assert [row["object_id"] for row in after_exclusion["results"]] == [
        visible["object_id"],
    ]
    assert after_exclusion["next_cursor"] is None
    with pytest.raises(NotFound):
        facts.publish(ctx, project_id, _body(project_id, hidden_evidence), uuid4())


def test_project_fact_sql_guard_immutability_and_stale_evidence(database, tenant):
    store, admin = database
    ctx, _, project_id, evidence_id = _prepared(store, tenant)
    facts = ProjectFacts(store)
    created = facts.publish(ctx, project_id, _body(project_id, evidence_id), uuid4())
    with pytest.raises(psycopg.Error):
        with store.transaction(ctx) as conn:
            conn.execute(
                "INSERT INTO knowledge_project_facts(tenant_id,id,project_id,predicate,"
                "value,value_type,assertion_status,confidence,evidence_ids,"
                "quote_evidence_id,source_quote,observed_at,reviewer_id) "
                "VALUES (%s,%s,%s,'capital.amount','forged','text','asserted',1,"
                "%s,%s,'invented source quote',%s,%s)",
                (ctx.tenant_id, "pfact_" + "0" * 32, project_id, [evidence_id],
                 evidence_id, NOW, ctx.actor_id),
            )
    with pytest.raises(psycopg.Error):
        with store.transaction(ctx) as conn:
            conn.execute(
                "UPDATE knowledge_project_facts SET value='changed' WHERE id=%s",
                (created["object_id"],),
            )
    with pytest.raises(psycopg.Error):
        with store.transaction(ctx) as conn:
            conn.execute("TRUNCATE knowledge_project_facts")
    with psycopg.connect(admin) as conn:
        conn.execute(
            "UPDATE brain_source_items i SET current_version_id=NULL "
            "FROM brain_source_versions v JOIN brain_evidence e "
            "ON e.tenant_id=v.tenant_id AND e.source_version_id=v.id "
            "WHERE i.tenant_id=v.tenant_id AND i.id=v.item_id "
            "AND e.tenant_id=%s AND e.id=%s",
            (ctx.tenant_id, evidence_id),
        )
    # This fixture also supplies the project basis; both project and fact
    # should fail closed rather than claiming a currently grounded row.
    with pytest.raises(NotFound):
        facts.publish(ctx, project_id, _body(project_id, evidence_id), uuid4())
    assert facts.page(ctx, project_id, ProjectFactPageRequest())["results"] == []


def test_project_fact_api_scopes_closed_request_and_dossier(database, tenant):
    store, _ = database
    ctx, _, project_id, evidence_id = _prepared(store, tenant)
    token = "fictional-project-fact-" + uuid4().hex
    path = f"/v1/knowledge/projects/{project_id}/facts"

    def client(scopes: set[str]) -> TestClient:
        credential = Credential(
            token_sha256=hashlib.sha256(token.encode()).hexdigest(),
            tenant_id=ctx.tenant_id, actor_id=ctx.actor_id, scopes=scopes,
            expires_at=datetime.now(UTC) + timedelta(hours=1), client_kind="human",
        )
        return TestClient(
            create_app(store, TokenRegistry([credential])),
            headers={"Authorization": "Bearer " + token},
        )

    payload = _body(project_id, evidence_id).model_dump(mode="json")
    with client({"knowledge.review"}) as denied:
        assert denied.post(
            path, json=payload, headers={"idempotency-key": str(uuid4())},
        ).status_code == 403
    with client({"knowledge.review", "brain.content.read", "knowledge.search"}) as api:
        created = api.post(
            path, json=payload, headers={"idempotency-key": str(uuid4())},
        )
        assert created.status_code == 201, created.text
        assert created.json()["reviewed"] is True
        page = api.get(path, params={"limit": 1})
        assert page.status_code == 200, page.text
        assert page.json()["results"][0]["object_id"] == created.json()["object_id"]
        assert page.headers["cache-control"] == "no-store"
        dossier = api.get(
            f"/v1/knowledge/projects/{project_id}/dossier", params={"fact_limit": 1},
        )
        assert dossier.status_code == 200, dossier.text
        assert dossier.json()["facts"][0]["object_id"] == created.json()["object_id"]
        assert dossier.json()["fact_limit"] == 1
        assert api.get(path, params={"limit": 0}).status_code == 422
        assert api.get(path, params={"after": "pfact_bad"}).status_code == 422
        assert api.post(
            path, json={**payload, "derivation": "inferred"},
            headers={"idempotency-key": str(uuid4())},
        ).status_code == 422
    with client({"knowledge.review"}) as denied:
        assert denied.get(path).status_code == 403


def test_project_fact_can_quote_fileos_but_requires_both_source_grants(
    database, tenant, tmp_path,
):
    store, _ = database
    ctx, _, project_id, email_evidence = _prepared(store, tenant)
    file_root = tmp_path / "fictional-project-fact-files"
    file_root.mkdir()
    file_text = "Synthetic Melron term sheet says 200 units."
    (file_root / "terms.txt").write_text(file_text, encoding="utf-8")
    manifest = pg.fileos_manifest(file_root, source_id="fictional_fact_files")
    core = pg.DataCoreStore(store)
    core.import_fileos_snapshot(ctx, manifest, uuid4())
    file_evidence = core.publish_text(
        ctx, manifest["items"][0]["version_id"], file_text,
        code_revision="project-fact-fictional-v1",
    ).evidence_id
    facts = ProjectFacts(store)
    first = facts.publish(
        ctx, project_id, _body(project_id, email_evidence), uuid4(),
    )
    mixed_basis = _body(
        project_id, file_evidence, quote="200 units", value="200 units",
    ).model_copy(update={
        "evidence_ids": [email_evidence, file_evidence],
        "supersedes_id": first["object_id"],
    })
    created = facts.publish(
        ctx, project_id, mixed_basis, uuid4(),
    )
    assert facts.page(ctx, project_id, ProjectFactPageRequest())["results"][0][
        "object_id"
    ] == created["object_id"]
    assert len(facts.page(ctx, project_id, ProjectFactPageRequest())["results"][0][
        "evidence_ids"
    ]) == 2
    with store.transaction(ctx) as conn:
        email_source = conn.execute(
            "SELECT v.source_id FROM brain_evidence e JOIN brain_source_versions v "
            "ON v.tenant_id=e.tenant_id AND v.id=e.source_version_id WHERE e.id=%s",
            (email_evidence,),
        ).fetchone()["source_id"]
    email_only = replace(ctx, source_ids=frozenset({email_source}))
    assert [row["object_id"] for row in facts.page(
        email_only, project_id, ProjectFactPageRequest(),
    )["results"]] == [first["object_id"]]
    assert [row["object_id"] for row in KnowledgeCore(store).project_dossier(
        email_only, project_id, ProjectDossierRequest(fact_limit=1),
    )["facts"]] == [first["object_id"]]
    with pytest.raises(NotFound):
        facts.publish(
            email_only, project_id,
            _body(project_id, file_evidence, quote="200 units"), uuid4(),
        )
    with pytest.raises(NotFound):
        facts.publish(
            email_only, project_id,
            _body(project_id, email_evidence, supersedes_id=created["object_id"]),
            uuid4(),
        )
