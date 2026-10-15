"""Fictional PostgreSQL proof of quoted project-fact publication and paging."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import httpx
import psycopg
import pytest
import test_postgres as pg
from fastapi.testclient import TestClient

from email_brain.api import create_app
from email_brain.auth import Credential, TokenRegistry
from email_brain.store import Conflict, NotFound, Store
from masterbrain.brain_client import BrainClientError, BrainReadClient
from masterbrain.fact_predicates import PROJECT_FACT_PREDICATES
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


def _source(store: Store, ctx: pg.TenantContext, account, key: str, cursor: str | None,
            body: str = QUOTE) -> str:
    store.ingest_page(ctx, account, cursor, key, [
        replace(pg.item(key, body=body), provider_id=key),
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
        kind="project_fact", project_id=project_id, predicate="deal.note",
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


def test_predicate_catalog_api_and_external_client_show_database_authority(database, tenant):
    store, _ = database
    ctx, _, _, _ = _prepared(store, tenant)
    token = "fictional-registry-" + uuid4().hex
    credential = Credential(
        token_sha256=hashlib.sha256(token.encode()).hexdigest(),
        tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
        scopes={"knowledge.search"},
        expires_at=datetime.now(UTC) + timedelta(hours=1), client_kind="human",
    )
    assistant_token = "fictional-registry-assistant-" + uuid4().hex
    denied_token = "fictional-registry-denied-" + uuid4().hex
    assistant = Credential(
        token_sha256=hashlib.sha256(assistant_token.encode()).hexdigest(),
        tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
        scopes={"knowledge.search"},
        expires_at=datetime.now(UTC) + timedelta(hours=1), client_kind="assistant",
        source_ids={"fictional_catalog_source"},
    )
    with pytest.raises(ValueError, match="source enrollment"):
        Credential(
            token_sha256=hashlib.sha256(uuid4().hex.encode()).hexdigest(),
            tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
            scopes={"knowledge.search"},
            expires_at=datetime.now(UTC) + timedelta(hours=1), client_kind="assistant",
            source_ids=None,
        )
    denied = Credential(
        token_sha256=hashlib.sha256(denied_token.encode()).hexdigest(),
        tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
        scopes={"brain.content.read"},
        expires_at=datetime.now(UTC) + timedelta(hours=1), client_kind="human",
    )
    with TestClient(create_app(store, TokenRegistry([
        credential, assistant, denied,
    ]))) as api:
        response = api.get(
            "/v1/knowledge/fact-predicates",
            headers={"Authorization": "Bearer " + token},
        )
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        catalog = response.json()
        assert catalog["scope"] == "new_project_fact_writes_only"
        assert catalog["historical_unregistered_rows_possible"] is True
        assert catalog["alias_mapping"] == "none"
        assert [(row["name"], row["status"]) for row in catalog["entries"]] == [
            (name, "active") for name in sorted(PROJECT_FACT_PREDICATES)
        ]
        assert api.get(
            "/v1/knowledge/fact-predicates",
            headers={"Authorization": "Bearer " + assistant_token},
        ).json() == catalog
        assert api.get(
            "/v1/knowledge/fact-predicates",
            headers={"Authorization": "Bearer " + denied_token},
        ).status_code == 403
        with BrainReadClient(
            "https://brain.example", "fictional-token",
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json=catalog)
            ),
        ) as reader:
            assert reader.project_fact_predicates() == catalog


def test_predicate_catalog_fails_closed_when_running_code_disagrees_with_sql(
    database, tenant, monkeypatch,
):
    store, _ = database
    ctx, _, _, _ = _prepared(store, tenant)
    monkeypatch.delitem(PROJECT_FACT_PREDICATES, "loi.price")
    with pytest.raises(RuntimeError, match="code/database mismatch"):
        ProjectFacts(store).predicate_catalog(ctx)


def test_project_fact_registry_matches_sql_and_blocks_unregistered_direct_writes(
    database, tenant,
):
    store, admin = database
    ctx, _, project_id, evidence_id = _prepared(store, tenant)
    existing = ProjectFacts(store).publish(
        ctx, project_id, _body(project_id, evidence_id), uuid4(),
    )
    with psycopg.connect(admin) as conn:
        rows = conn.execute(
            "SELECT name,version,value_type,unit_code,description,status "
            "FROM knowledge_project_fact_predicates ORDER BY name"
        ).fetchall()
        assert rows == [
            (name, spec.version, spec.value_type, spec.unit, spec.description, "active")
            for name, spec in sorted(PROJECT_FACT_PREDICATES.items())
        ]
        version = conn.execute(
            "SELECT predicate_registry_version FROM knowledge_project_facts "
            "WHERE tenant_id=%s AND id=%s", (ctx.tenant_id, existing["object_id"]),
        ).fetchone()
        assert version == (1,)
    with pytest.raises(psycopg.errors.RaiseException), psycopg.connect(admin) as conn:
        conn.execute(
            "UPDATE knowledge_project_fact_predicates SET description='forged' "
            "WHERE name='deal.note' AND version=1"
        )
    for suffix, name in (("9", "unlisted.note"), ("8", "capital.amount")):
        with pytest.raises(psycopg.errors.RaiseException, match="registered shape"):
            with store.transaction(ctx) as conn:
                conn.execute(
                    "INSERT INTO knowledge_project_facts(tenant_id,id,project_id,predicate,"
                    "value,value_type,assertion_status,confidence,derivation,evidence_ids,"
                    "quote_evidence_id,source_quote,observed_at,reviewer_id) "
                    "SELECT tenant_id,%s,project_id,%s,value,value_type,"
                    "assertion_status,confidence,derivation,evidence_ids,"
                    "quote_evidence_id,source_quote,observed_at,reviewer_id "
                    "FROM knowledge_project_facts WHERE id=%s",
                    ("pfact_" + suffix * 32, name, existing["object_id"]),
                )


def test_registry_change_preserves_exact_reviewed_idempotent_replay(
    database, tenant, monkeypatch,
):
    store, _ = database
    ctx, _, project_id, evidence_id = _prepared(store, tenant)
    facts = ProjectFacts(store)
    body = _body(project_id, evidence_id)
    key = uuid4()
    first = facts.publish(ctx, project_id, body, key)
    monkeypatch.delitem(PROJECT_FACT_PREDICATES, "deal.note")
    assert facts.publish(ctx, project_id, body, key) == {**first, "changed": False}
    with pytest.raises(ValueError, match="registry review"):
        facts.publish(ctx, project_id, body, uuid4())


def test_project_fact_exact_measurement_stays_typed_only_in_report(database, tenant):
    store, admin = database
    ctx, account, project_id, evidence_id = _prepared(store, tenant)
    facts = ProjectFacts(store)
    legacy = facts.publish(ctx, project_id, _body(project_id, evidence_id), uuid4())
    amount_quote = "Fictional amount 100.25 USD"
    amount_evidence = _source(
        store, ctx, account, "fictional-typed-fact-message",
        "fictional-fact-message-1", body=amount_quote,
    )
    body = ProjectFactWrite.model_validate({
        **_body(project_id, amount_evidence, value="100.25", quote=amount_quote).model_dump(),
        "predicate": "capital.amount",
        "value_type": "number",
        "measurement": {"amount": "100.25", "unit": "currency", "currency": "USD"},
    })
    typed = facts.publish(ctx, project_id, body, uuid4())
    report = facts.report(ctx, project_id, ProjectFactPageRequest())
    by_id = {row["object_id"]: row for group in report["groups"] for row in group["facts"]}
    assert by_id[legacy["object_id"]]["measurement"] is None
    assert by_id[typed["object_id"]]["measurement"] == {
        "amount": "100.25", "unit": "currency", "currency": "USD",
        "meaning": "reviewed_source_stated_not_balance",
    }
    assert "measurement" not in facts.page(ctx, project_id, ProjectFactPageRequest())[
        "results"
    ][0]
    assert report["numeric_aggregation"] == "none_units_currency_ownership_unverified"
    token = "fictional-typed-fact-" + uuid4().hex
    credential = Credential(
        token_sha256=hashlib.sha256(token.encode()).hexdigest(),
        tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
        scopes={"knowledge.search"},
        expires_at=datetime.now(UTC) + timedelta(hours=1), client_kind="human",
    )
    with TestClient(create_app(store, TokenRegistry([credential]))) as api:
        response = api.get(
            f"/v1/knowledge/projects/{project_id}/facts/report",
            params={"limit": 10},
            headers={"Authorization": "Bearer " + token},
        )
        assert response.status_code == 200, response.text
        with BrainReadClient(
            "https://brain.example", "fictional-token",
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json=response.json())
            ),
        ) as reader:
            assert any(
                row["measurement"] is not None
                for group in reader.project_fact_report(project_id, limit=10)["groups"]
                for row in group["facts"]
            )
    with psycopg.connect(admin) as conn:
        row = conn.execute(
            "SELECT amount_decimal,unit_code,currency_code FROM knowledge_project_facts "
            "WHERE tenant_id=%s AND id=%s", (ctx.tenant_id, typed["object_id"]),
        ).fetchone()
    assert row == (Decimal("100.25"), "currency", "USD")
    with pytest.raises(psycopg.errors.CheckViolation), psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO knowledge_project_facts(tenant_id,id,project_id,predicate,"
            "value,value_type,assertion_status,confidence,derivation,evidence_ids,"
            "quote_evidence_id,source_quote,observed_at,reviewer_id,amount_decimal,"
            "unit_code,currency_code) SELECT tenant_id,%s,project_id,predicate,"
            "value,value_type,assertion_status,confidence,derivation,evidence_ids,"
            "quote_evidence_id,source_quote,observed_at,reviewer_id,amount_decimal,"
            "unit_code,'usd' FROM knowledge_project_facts WHERE tenant_id=%s AND id=%s",
            ("pfact_" + "f" * 32, ctx.tenant_id, typed["object_id"]),
        )
    with pytest.raises(psycopg.errors.CheckViolation), psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO knowledge_project_facts(tenant_id,id,project_id,predicate,"
            "value,value_type,assertion_status,confidence,derivation,evidence_ids,"
            "quote_evidence_id,source_quote,observed_at,reviewer_id,amount_decimal,"
            "unit_code,currency_code) SELECT tenant_id,%s,project_id,predicate,"
            "'200.00',value_type,assertion_status,confidence,derivation,evidence_ids,"
            "quote_evidence_id,source_quote,observed_at,reviewer_id,200.00,"
            "unit_code,currency_code FROM knowledge_project_facts "
            "WHERE tenant_id=%s AND id=%s",
            ("pfact_" + "e" * 32, ctx.tenant_id, typed["object_id"]),
        )
    for suffix, unit, currency in (("d", None, "USD"), ("c", "currency", None)):
        expected = (psycopg.errors.RaiseException if unit is None
                    else psycopg.errors.CheckViolation)
        with pytest.raises(expected), psycopg.connect(admin) as conn:
            conn.execute(
                "INSERT INTO knowledge_project_facts(tenant_id,id,project_id,predicate,"
                "value,value_type,assertion_status,confidence,derivation,evidence_ids,"
                "quote_evidence_id,source_quote,observed_at,reviewer_id,amount_decimal,"
                "unit_code,currency_code) SELECT tenant_id,%s,project_id,predicate,"
                "value,value_type,assertion_status,confidence,derivation,evidence_ids,"
                "quote_evidence_id,source_quote,observed_at,reviewer_id,amount_decimal,"
                "%s,%s FROM knowledge_project_facts WHERE tenant_id=%s AND id=%s",
                ("pfact_" + suffix * 32, unit, currency, ctx.tenant_id, typed["object_id"]),
            )
    misleading = _source(
        store, ctx, account, "fictional-measurement-fragments",
        "fictional-typed-fact-message",
        body="Fictional amount 1100.25 USD. Fictional amount 100.25 USDA.",
    )
    for suffix, quote in (("b", "Fictional amount 1100.25 USD"),
                          ("a", "Fictional amount 100.25 USDA")):
        with pytest.raises(psycopg.errors.CheckViolation), psycopg.connect(admin) as conn:
            conn.execute(
                "INSERT INTO knowledge_project_facts(tenant_id,id,project_id,predicate,"
                "value,value_type,assertion_status,confidence,derivation,evidence_ids,"
                "quote_evidence_id,source_quote,observed_at,reviewer_id,amount_decimal,"
                "unit_code,currency_code) SELECT tenant_id,%s,project_id,predicate,"
                "value,value_type,assertion_status,confidence,derivation,ARRAY[%s],"
                "%s,%s,observed_at,reviewer_id,amount_decimal,"
                "unit_code,currency_code FROM knowledge_project_facts "
                "WHERE tenant_id=%s AND id=%s",
                ("pfact_" + suffix * 32, misleading, misleading, quote,
                 ctx.tenant_id, typed["object_id"]),
            )


def test_project_fact_markdown_byte_budget_preserves_paging(database, tenant):
    store, _ = database
    ctx, _, project_id, evidence_id = _prepared(store, tenant)
    facts = ProjectFacts(store)
    for _ in range(30):
        facts.publish(
            ctx, project_id,
            _body(project_id, evidence_id, value="\x01" * 4000), uuid4(),
        )
    first = facts.export_markdown(ctx, project_id, ProjectFactPageRequest(limit=25))
    assert 1 <= first["fact_count"] < 25
    assert first["next_cursor"] is not None
    assert len(first["markdown"].encode("utf-8")) <= 32_768
    assert facts.export_markdown(
        ctx, project_id, ProjectFactPageRequest(
            limit=25, recorded_cutoff_at=first["recorded_cutoff_at"],
        ),
    )["markdown"] == first["markdown"]
    total = first["fact_count"]
    cursor = first["next_cursor"]
    while cursor is not None:
        page = facts.export_markdown(
            ctx, project_id, ProjectFactPageRequest(
                limit=25, recorded_cutoff_at=first["recorded_cutoff_at"],
                after=cursor,
            ),
        )
        assert page["fact_count"] > 0
        assert len(page["markdown"].encode("utf-8")) <= 32_768
        total += page["fact_count"]
        assert page["next_cursor"] != cursor
        cursor = page["next_cursor"]
    assert total == 30


def test_project_fact_exact_quote_replay_and_visible_successor(database, tenant):
    store, admin = database
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
    exported = facts.export_markdown(ctx, project_id, ProjectFactPageRequest())
    assert exported["fact_count"] == 1
    assert exported["next_cursor"] is None
    assert first["object_id"] in exported["markdown"]
    assert evidence_id in exported["markdown"]
    assert QUOTE in exported["markdown"]
    assert "partial export" in exported["markdown"]
    assert len(exported["markdown"].encode("utf-8")) <= 32_768
    assert facts.export_markdown(
        ctx, project_id,
        ProjectFactPageRequest(recorded_cutoff_at=exported["recorded_cutoff_at"]),
    )["markdown"] == exported["markdown"]
    with psycopg.connect(admin) as conn:
        audit = conn.execute(
            "SELECT resource_type,resource_id,metadata FROM audit_events "
            "WHERE tenant_id=%s AND event_type='knowledge.project_facts_markdown_export' "
            "ORDER BY occurred_at DESC LIMIT 1",
            (ctx.tenant_id,),
        ).fetchone()
    assert audit == ("project", None, {})
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


def test_transactional_fact_publication_rolls_back_whole_review(database, tenant):
    store, _ = database
    ctx, _, project_id, evidence_id = _prepared(store, tenant)
    facts = ProjectFacts(store)
    first_key = uuid4()
    with pytest.raises(ValueError, match="quote lacks"):
        with store.transaction(ctx) as conn:
            facts._publish_in_transaction(
                conn, ctx, project_id, _body(project_id, evidence_id), first_key,
            )
            facts._publish_in_transaction(
                conn, ctx, project_id,
                _body(project_id, evidence_id, quote="invented"), uuid4(),
            )
    assert facts.page(ctx, project_id, ProjectFactPageRequest())["results"] == []
    published = facts.publish(ctx, project_id, _body(project_id, evidence_id), first_key)
    assert published["changed"] is True


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
        facts.export_markdown(foreign_ctx, project_id, ProjectFactPageRequest())
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
    restricted_report = facts.report(scoped, project_id, ProjectFactPageRequest(limit=1))
    assert [row["object_id"] for group in restricted_report["groups"]
            for row in group["facts"]] == [visible["object_id"]]
    assert restricted_report["next_cursor"] is None
    restricted_export = facts.export_markdown(
        scoped, project_id, ProjectFactPageRequest(limit=1),
    )
    assert restricted_export["fact_count"] == 1
    assert restricted_export["next_cursor"] is None
    assert visible["object_id"] in restricted_export["markdown"]
    assert "Hidden fictional value" not in restricted_export["markdown"]
    restricted_dossier = KnowledgeCore(store).project_dossier(
        scoped, project_id, ProjectDossierRequest(fact_limit=1),
    )
    assert [row["object_id"] for row in restricted_dossier["facts"]] == [
        visible["object_id"],
    ]
    assert restricted_dossier["facts_truncated"] is False
    unrestricted = facts.page(ctx, project_id, ProjectFactPageRequest(limit=1))
    assert unrestricted["next_cursor"] is not None
    assert facts.report(ctx, project_id, ProjectFactPageRequest(limit=1))[
        "groups"
    ][0]["comparison_incomplete"] is True
    unrestricted_export = facts.export_markdown(
        ctx, project_id, ProjectFactPageRequest(limit=1),
    )
    assert unrestricted_export["next_cursor"] is not None
    next_export = facts.export_markdown(
        ctx, project_id, ProjectFactPageRequest(
            limit=1, recorded_cutoff_at=unrestricted_export["recorded_cutoff_at"],
            after=unrestricted_export["next_cursor"],
        ),
    )
    assert next_export["fact_count"] == 1
    with pytest.raises(NotFound):
        facts.export_markdown(scoped, project_id, ProjectFactPageRequest(
            limit=1, recorded_cutoff_at=unrestricted_export["recorded_cutoff_at"],
            after=unrestricted_export["next_cursor"],
        ))
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
    assert facts.report(ctx, project_id, ProjectFactPageRequest(limit=1))[
        "next_cursor"
    ] is None
    assert "Hidden fictional value" not in facts.export_markdown(
        ctx, project_id, ProjectFactPageRequest(limit=1),
    )["markdown"]
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
    assert facts.report(ctx, project_id, ProjectFactPageRequest())["groups"] == []


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
        exported = api.get(path + "/markdown", params={"limit": 1})
        assert exported.status_code == 200, exported.text
        assert exported.headers["cache-control"] == "no-store"
        assert exported.json()["fact_count"] == 1
        assert evidence_id in exported.json()["markdown"]
        report = api.get(path + "/report", params={"limit": 1})
        assert report.status_code == 200, report.text
        assert report.headers["cache-control"] == "no-store"
        assert report.json()["groups"][0]["facts"][0]["object_id"] == (
            created.json()["object_id"]
        )
        assert report.json()["numeric_aggregation"] == (
            "none_units_currency_ownership_unverified"
        )
        with BrainReadClient(
            "https://brain.example", "fictional-token",
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json=report.json())
            ),
        ) as reader:
            assert reader.project_fact_report(project_id, limit=1)["groups"][0][
                "facts"
            ][0]["object_id"] == created.json()["object_id"]
        falsified = {**report.json(), "numeric_aggregation": "verified_investment_total"}
        with BrainReadClient(
            "https://brain.example", "fictional-token",
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json=falsified)
            ),
        ) as reader, pytest.raises(BrainClientError, match="invalid_response"):
            reader.project_fact_report(project_id, limit=1)
        with BrainReadClient(
            "https://brain.example", "fictional-token",
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json=exported.json())
            ),
        ) as reader:
            assert reader.project_fact_markdown(project_id, limit=1)[
                "markdown"
            ] == exported.json()["markdown"]
        assert api.get(path, params={"limit": 0}).status_code == 422
        assert api.get(path + "/markdown", params={"limit": 0}).status_code == 422
        assert api.get(path + "/report", params={"limit": 0}).status_code == 422
        assert api.get(path, params={"after": "pfact_bad"}).status_code == 422
        assert api.post(
            path, json={**payload, "derivation": "inferred"},
            headers={"idempotency-key": str(uuid4())},
        ).status_code == 422
    with client({"knowledge.review"}) as denied:
        assert denied.get(path).status_code == 403
        assert denied.get(path + "/report").status_code == 403
    with client({"knowledge.search"}) as denied:
        assert denied.get(path + "/markdown").status_code == 403
    with client({"brain.content.read"}) as denied:
        assert denied.get(path + "/markdown").status_code == 403


def test_project_fact_markdown_assistant_enrollment_filters_before_export(database, tenant):
    store, _ = database
    ctx, _, project_id, evidence_id = _prepared(store, tenant)
    ProjectFacts(store).publish(
        ctx, project_id, _body(project_id, evidence_id), uuid4(),
    )
    with store.transaction(ctx) as conn:
        source_id = conn.execute(
            "SELECT v.source_id FROM brain_evidence e JOIN brain_source_versions v "
            "ON v.tenant_id=e.tenant_id AND v.id=e.source_version_id WHERE e.id=%s",
            (evidence_id,),
        ).fetchone()["source_id"]
    token = "fictional-fact-assistant-" + uuid4().hex

    def client(source_ids: set[str]) -> TestClient:
        credential = Credential(
            token_sha256=hashlib.sha256(token.encode()).hexdigest(),
            tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
            scopes={"knowledge.search", "brain.content.read"},
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            client_kind="assistant", source_ids=source_ids,
        )
        return TestClient(
            create_app(store, TokenRegistry([credential])),
            headers={"Authorization": "Bearer " + token},
        )

    with client({source_id}) as allowed:
        response = allowed.get(f"/v1/knowledge/projects/{project_id}/facts/markdown")
        assert response.status_code == 200, response.text
        assert evidence_id in response.json()["markdown"]
        report = allowed.get(f"/v1/knowledge/projects/{project_id}/facts/report")
        assert report.status_code == 200, report.text
        assert report.json()["groups"][0]["facts"][0]["quote_evidence_id"] == evidence_id
    with client({"fictional_other_source"}) as hidden:
        response = hidden.get(f"/v1/knowledge/projects/{project_id}/facts/markdown")
        assert response.status_code == 404
        assert hidden.get(
            f"/v1/knowledge/projects/{project_id}/facts/report"
        ).status_code == 404
    with pytest.raises(ValueError):
        client(set())


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
    scoped_export = facts.export_markdown(
        email_only, project_id, ProjectFactPageRequest(),
    )
    assert first["object_id"] in scoped_export["markdown"]
    assert created["object_id"] not in scoped_export["markdown"]
    assert file_evidence not in scoped_export["markdown"]
    full_export = facts.export_markdown(ctx, project_id, ProjectFactPageRequest())
    assert created["object_id"] in full_export["markdown"]
    assert file_evidence in full_export["markdown"]
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
