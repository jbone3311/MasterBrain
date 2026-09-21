"""Adversarial virtual-rule control acceptance; synthetic inputs and disposable PG only."""

import hashlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from test_postgres import database as database
from test_postgres import tenant as tenant

from email_brain.api import create_app
from email_brain.auth import Credential, Principal, TokenRegistry
from email_brain.domain.models import TenantContext
from email_brain.rules.active import classify
from email_brain.rules.control import RuleControl
from email_brain.schemas import FeaturePayload, ProposalRequest, ReviewRequest, RulePayload
from email_brain.store import AccessDenied, Conflict, IngestItem, NotFound, Store


def proposed_rule(store, context, *, domain="example.invalid", approve=True):
    proposal = store.propose(
        context,
        ProposalRequest(
            payload=RulePayload(
                kind="rule",
                sender_domain=domain,
                category="synthetic-review",
                canonical_mailbox="review_delete",
            ),
            reason="Synthetic owner request",
            source="security-test",
        ),
        uuid4(),
    )
    if approve:
        store.review(
            context, proposal["id"], ReviewRequest(decision="approved", expected_version=1)
        )
    return proposal["id"]


@pytest.mark.parametrize("operation", ["simulate", "activate", "rollback"])
@pytest.mark.parametrize(
    "kind,scopes",
    [
        ("assistant", frozenset({"email.review", "email.search"})),
        ("worker", frozenset({"email.review", "email.search"})),
        ("human", frozenset({"email.review"})),
        ("human", frozenset({"email.search"})),
    ],
)
def test_rule_mutations_deny_nonhuman_or_partial_scopes_before_database(operation, kind, scopes):
    context = TenantContext(uuid4(), uuid4(), scopes, uuid4())
    control = RuleControl(Store("not-a-real-dsn"))
    principal = Principal(context, kind)
    with patch("psycopg.connect") as connect:
        with pytest.raises(AccessDenied):
            if operation == "simulate":
                control.simulate(principal, uuid4(), 2)
            elif operation == "activate":
                control.activate(principal, uuid4())
            else:
                control.rollback(principal, 1, 0)
        connect.assert_not_called()


@pytest.mark.parametrize(
    "sender,matched",
    [
        ("person@example.invalid", True),
        ("person@EXAMPLE.INVALID", True),
        ("person@evil-example.invalid", False),
        ("person@sub.example.invalid", False),
        ("person@example.invalid.evil.invalid", False),
        ("person@example.invalid, other@evil.invalid", False),
    ],
)
def test_virtual_rule_domain_is_exact_not_substring_or_multi_sender(sender, matched):
    result = classify(
        [
            {
                "proposal_id": str(uuid4()),
                "version": 2,
                "payload": {
                    "kind": "rule",
                    "sender_domain": "example.invalid",
                    "category": "synthetic",
                    "canonical_mailbox": "review_delete",
                },
            }
        ],
        7,
        sender,
    )
    assert bool(result["effects"]) is matched
    assert result["virtual_only"] is True and result["rules_revision"] == 7
    assert not {"deleted", "mailbox_ids", "send", "execute"} & result["effects"].keys()


@pytest.mark.postgres
@pytest.mark.parametrize("state", ["pending", "rejected", "non-rule"])
def test_only_approved_rule_lane_can_be_simulated(database, tenant, state):
    store, _ = database
    context, _ = tenant
    control = RuleControl(store)
    if state == "non-rule":
        proposal = store.propose(
            context,
            ProposalRequest(
                payload=FeaturePayload(
                    kind="feature", title="Synthetic feature", desired_outcome="Never execute"
                ),
                reason="Synthetic",
                source="security-test",
            ),
            uuid4(),
        )["id"]
        store.review(context, proposal, ReviewRequest(decision="approved", expected_version=1))
    else:
        proposal = proposed_rule(store, context, approve=False)
        if state == "rejected":
            store.review(context, proposal, ReviewRequest(decision="rejected", expected_version=1))
    with pytest.raises(Conflict):
        control.simulate(Principal(context, "human"), proposal, 1 if state == "pending" else 2)
    assert control.list(context)["revision"] == 0


@pytest.mark.postgres
def test_simulation_bound_to_exact_human_actor_even_for_another_owner(database, tenant):
    store, administrator = database
    context, _ = tenant
    control = RuleControl(store)
    proposal = proposed_rule(store, context)
    receipt = control.simulate(Principal(context, "human"), proposal, 2)
    another_actor = uuid4()
    with psycopg.connect(administrator) as connection:
        connection.execute(
            "INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES (%s,%s,'owner')",
            (context.tenant_id, another_actor),
        )
    another_owner = Principal(replace(context, actor_id=another_actor), "human")
    with pytest.raises(NotFound):
        control.activate(another_owner, receipt["id"])
    assert control.list(context)["revision"] == 0


@pytest.mark.postgres
def test_competing_simulations_have_one_cas_winner(database, tenant):
    store, _ = database
    context, _ = tenant
    control, principal = RuleControl(store), Principal(context, "human")
    receipts = [
        control.simulate(principal, proposed_rule(store, context, domain=domain), 2)
        for domain in ("one.example.invalid", "two.example.invalid")
    ]
    assert all(receipt["base_revision"] == 0 for receipt in receipts)

    def activate(receipt):
        try:
            return control.activate(principal, receipt["id"])["revision"]
        except Conflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(activate, receipts))
    assert sorted(map(str, results)) == ["1", "conflict"]
    assert control.list(context)["revision"] == 1


@pytest.mark.postgres
def test_activation_replay_after_rollback_never_reactivates_old_rule(database, tenant):
    store, _ = database
    context, _ = tenant
    control, principal = RuleControl(store), Principal(context, "human")
    receipt = control.simulate(principal, proposed_rule(store, context), 2)
    assert control.activate(principal, receipt["id"])["revision"] == 1
    assert control.rollback(principal, 1, 0)["revision"] == 2
    replay = control.activate(principal, receipt["id"])
    assert replay["replayed"] and replay["revision"] == 1
    current = control.list(context)
    assert current["revision"] == 2 and current["rules"] == []
    assert current["mailbox_effects"] is False
    with store.transaction(context) as connection:
        assert connection.execute("SELECT count(*) AS n FROM rule_revisions").fetchone()["n"] == 2


@pytest.mark.postgres
def test_expired_simulation_cannot_activate(database, tenant):
    store, _ = database
    context, _ = tenant
    control, principal = RuleControl(store), Principal(context, "human")
    receipt = control.simulate(principal, proposed_rule(store, context), 2)
    # Seed an already-expired synthetic receipt without rewriting immutable history.
    with store.transaction(context) as connection:
        expired = connection.execute(
            "INSERT INTO rule_simulations(tenant_id,actor_id,proposal_id,proposal_version,"
            "proposal_hash,base_revision,sample,created_at,expires_at) "
            "SELECT tenant_id,actor_id,proposal_id,proposal_version,proposal_hash,"
            "base_revision,sample,now()-interval '20 minutes',now()-interval '5 minutes' "
            "FROM rule_simulations WHERE id=%s RETURNING id",
            (receipt["id"],),
        ).fetchone()["id"]
    with pytest.raises(Conflict):
        control.activate(principal, expired)
    assert control.list(context)["revision"] == 0


@pytest.mark.postgres
def test_rule_receipts_and_revisions_cannot_be_rewritten_by_runtime(database, tenant):
    store, _ = database
    context, _ = tenant
    control, principal = RuleControl(store), Principal(context, "human")
    receipt = control.simulate(principal, proposed_rule(store, context), 2)
    control.activate(principal, receipt["id"])
    for table in ("rule_simulations", "rule_revisions"):
        for operation in ("UPDATE", "DELETE"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with store.transaction(context) as connection:
                    statement = (
                        psycopg.sql.SQL("UPDATE {} SET actor_id=actor_id")
                        if operation == "UPDATE"
                        else psycopg.sql.SQL("DELETE FROM {}")
                    )
                    connection.execute(statement.format(psycopg.sql.Identifier(table)))


@pytest.mark.postgres
def test_foreign_owner_cannot_read_activate_or_reference_rule_receipt(database, tenant):
    store, administrator = database
    context, _ = tenant
    control, principal = RuleControl(store), Principal(context, "human")
    proposal = proposed_rule(store, context)
    receipt = control.simulate(principal, proposal, 2)
    control.activate(principal, receipt["id"])
    foreign_tenant, foreign_actor = uuid4(), uuid4()
    with psycopg.connect(administrator) as connection:
        connection.execute(
            "INSERT INTO tenants(id,name) VALUES (%s,'Synthetic foreign rule owner')",
            (foreign_tenant,),
        )
        connection.execute(
            "INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES (%s,%s,'owner')",
            (foreign_tenant, foreign_actor),
        )
        rows = connection.execute(
            "SELECT relrowsecurity,relforcerowsecurity FROM pg_class "
            "WHERE relname IN ('rule_simulations','rule_revisions') AND relkind='r'"
        ).fetchall()
        assert len(rows) == 2 and all(enabled and forced for enabled, forced in rows)
    foreign_context = replace(context, tenant_id=foreign_tenant, actor_id=foreign_actor)
    foreign = Principal(foreign_context, "human")
    assert control.list(foreign_context)["revision"] == 0
    with pytest.raises(NotFound):
        control.simulate(foreign, proposal, 2)
    with pytest.raises(NotFound):
        control.activate(foreign, receipt["id"])
    with store.transaction(foreign_context) as connection:
        assert not connection.execute("SELECT 1 FROM rule_simulations").fetchone()
        assert not connection.execute("SELECT 1 FROM rule_revisions").fetchone()
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with store.transaction(foreign_context) as connection:
            connection.execute(
                "INSERT INTO rule_revisions(tenant_id,revision,actor_id,rules,simulation_id) "
                "VALUES (%s,1,%s,'[]'::jsonb,%s)",
                (foreign_tenant, foreign_actor, receipt["id"]),
            )


@pytest.mark.postgres
def test_rest_rule_review_simulation_activation_and_rollback_are_virtual_only(database, tenant):
    store, _ = database
    context, account = tenant
    owner_token = "synthetic-rest-owner-token-never-valid"
    assistant_token = "synthetic-rest-assistant-token-never-valid"
    credentials = TokenRegistry(
        [
            Credential(
                token_sha256=hashlib.sha256(token.encode()).hexdigest(),
                tenant_id=context.tenant_id,
                actor_id=context.actor_id,
                scopes=scopes,
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                client_kind=kind,
            )
            for token, kind, scopes in (
                (owner_token, "human", set(context.scopes)),
                (assistant_token, "assistant", {"email.proposal.create"}),
            )
        ]
    )
    raw = b"From: person@example.invalid\r\nSubject: Virtualcanary\r\n\r\nKeep this evidence."
    store.ingest_page(
        context,
        account,
        None,
        "synthetic-http-seeded",
        [IngestItem("rest-event", "rest-message", "v1", datetime(2026, 9, 20, tzinfo=UTC), raw)],
    )
    with store.transaction(context) as connection:
        original = connection.execute(
            "SELECT provider_version,raw_sha256,deleted,quarantined FROM messages"
        ).fetchone()
    client = TestClient(create_app(store, credentials))
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    proposal_response = client.post(
        "/v1/proposals",
        json={
            "payload": {
                "kind": "rule",
                "sender_domain": "example.invalid",
                "category": "synthetic-review",
                "canonical_mailbox": "review_delete",
            },
            "reason": "Synthetic reviewed REST workflow",
            "source": "security-rest-test",
        },
        headers={**owner_headers, "Idempotency-Key": str(uuid4())},
    )
    assert proposal_response.status_code == 201
    proposal_id = proposal_response.json()["id"]
    approved = client.post(
        f"/v1/proposals/{proposal_id}/reviews",
        json={"decision": "approved", "expected_version": 1},
        headers=owner_headers,
    )
    assert approved.status_code == 200 and approved.json()["applied"] is False
    assert approved.json()["proposal"]["version"] == 2
    simulated = client.post(
        f"/v1/proposals/{proposal_id}/simulation",
        json={"expected_version": 2},
        headers=owner_headers,
    )
    assert simulated.status_code == 201
    receipt = simulated.json()
    assert receipt["coverage"] == "bounded_sample" and receipt["mailbox_effects"] is False
    assert len(receipt["sample"]) == 1
    activation_body = {"simulation_id": receipt["id"]}
    denied = client.post(
        "/v1/rules/activations",
        json=activation_body,
        headers={"Authorization": f"Bearer {assistant_token}"},
    )
    assert denied.status_code == 403
    for route, body, extra in (
        (f"/v1/proposals/{proposal_id}/simulation", {"expected_version": 2}, "tenant_id"),
        ("/v1/rules/activations", activation_body, "actor_id"),
        ("/v1/rules/rollback", {"expected_revision": 1, "target_revision": 0}, "execute"),
    ):
        invalid = client.post(route, json={**body, extra: str(uuid4())}, headers=owner_headers)
        assert invalid.status_code == 422 and invalid.json() == {"error": "invalid_request"}
    assert client.get("/v1/rules", headers=owner_headers).json()["revision"] == 0
    activated = client.post("/v1/rules/activations", json=activation_body, headers=owner_headers)
    assert activated.status_code == 200
    assert activated.json()["revision"] == 1 and activated.json()["mailbox_effects"] is False
    found = client.post("/v1/search", json={"query": "Virtualcanary"}, headers=owner_headers)
    assert found.status_code == 200 and len(found.json()["results"]) == 1
    classification = found.json()["results"][0]["classification"]
    assert classification["virtual_only"] and classification["rules_revision"] == 1
    assert classification["effects"]["canonical_mailbox"] == "review_delete"
    rolled_back = client.post(
        "/v1/rules/rollback",
        json={"expected_revision": 1, "target_revision": 0},
        headers=owner_headers,
    )
    assert rolled_back.status_code == 200 and rolled_back.json()["revision"] == 2
    again = client.post("/v1/search", json={"query": "Virtualcanary"}, headers=owner_headers)
    assert len(again.json()["results"]) == 1
    assert again.json()["results"][0]["classification"]["effects"] == {}
    assert again.json()["results"][0]["classification"]["rules_revision"] == 2
    with store.transaction(context) as connection:
        assert (
            connection.execute(
                "SELECT provider_version,raw_sha256,deleted,quarantined FROM messages"
            ).fetchone()
            == original
        )
        assert connection.execute("SELECT count(*) AS n FROM provider_events").fetchone()["n"] == 1


@pytest.mark.postgres
def test_rule_simulation_sample_is_bounded_and_excludes_deleted_and_quarantined(database, tenant):
    store, _ = database
    context, account = tenant
    items = [
        IngestItem(
            f"sample-event-{index}",
            f"sample-message-{index}",
            "v1",
            datetime(2026, 9, 20, tzinfo=UTC),
            f"From: person@example.invalid\r\nSubject: Sample {index}\r\n\r\nSynthetic.".encode(),
        )
        for index in range(54)
    ]
    assert store.ingest_page(context, account, None, "sample1", items) == 54
    store.ingest_page(
        context,
        account,
        "sample1",
        "sample2",
        [
            replace(items[0], event_key="sample-delete", raw=None),
            replace(items[1], event_key="sample-quarantine", raw=b""),
        ],
    )
    control = RuleControl(store)
    receipt = control.simulate(Principal(context, "human"), proposed_rule(store, context), 2)
    assert receipt["coverage"] == "bounded_sample" and receipt["mailbox_effects"] is False
    assert len(receipt["sample"]) == 50
    with store.transaction(context) as connection:
        expected_ids = [
            str(row["id"])
            for row in connection.execute(
                "SELECT id FROM messages WHERE NOT deleted AND NOT quarantined ORDER BY id LIMIT 50"
            ).fetchall()
        ]
        excluded_ids = {
            str(row["id"])
            for row in connection.execute(
                "SELECT id FROM messages WHERE deleted OR quarantined"
            ).fetchall()
        }
    actual_ids = [row["message_id"] for row in receipt["sample"]]
    assert actual_ids == expected_ids and not excluded_ids.intersection(actual_ids)
    assert all(row["before"] == {} for row in receipt["sample"])
    assert all(row["after"]["canonical_mailbox"] == "review_delete" for row in receipt["sample"])
    assert control.list(context)["revision"] == 0  # A preview does not activate its proposal.
