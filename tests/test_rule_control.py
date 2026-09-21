"""Real database feedback loop plus deterministic exact-domain contract checks."""

from uuid import uuid4

import pytest
import test_postgres as pg
from pydantic import ValidationError

from email_brain.auth import Principal
from email_brain.rules.active import classify
from email_brain.rules.control import RuleControl
from email_brain.schemas import ProposalRequest, ReviewRequest, RulePayload, SearchRequest
from email_brain.store import Conflict

database, tenant = pg.database, pg.tenant


def rule(domain="example.invalid", category="investment", mailbox="review"):
    return RulePayload(
        kind="rule", sender_domain=domain, category=category, canonical_mailbox=mailbox
    )


def approved(store, ctx, payload=None):
    proposal = store.propose(
        ctx, ProposalRequest(payload=payload or rule(), reason="Synthetic", source="test"), uuid4()
    )
    return store.review(ctx, proposal["id"], ReviewRequest(decision="approved", expected_version=1))


@pytest.mark.postgres
def test_review_simulate_activate_search_replace_rollback(database, tenant):
    store, admin = database
    ctx, account = tenant
    human, control = Principal(ctx, "human"), RuleControl(store)
    store.ingest_page(ctx, account, None, "s1", [pg.item()])
    proposal = approved(store, ctx)
    assert control.list(ctx)["revision"] == 0
    assert store.search(ctx, SearchRequest(query="Melron"))[0]["classification"]["effects"] == {}
    receipt = control.simulate(human, proposal["id"], 2)
    assert receipt["sample"][0]["before"] == {}
    assert receipt["sample"][0]["after"]["category"] == "investment"
    assert receipt["coverage"] == "bounded_sample" and not receipt["mailbox_effects"]
    assert control.activate(human, receipt["id"])["revision"] == 1
    hit = store.search(ctx, SearchRequest(query="Melron"))[0]
    assert hit["classification"]["rules_revision"] == 1
    assert hit["classification"]["effects"]["category"] == "investment"
    assert hit["classification"]["virtual_only"]
    original = store.evidence(ctx, hit["evidence_id"])
    replacement = approved(store, ctx, rule(category="promotion", mailbox="review_delete"))
    second = control.simulate(human, replacement["id"], 2)
    result = control.activate(human, second["id"])
    assert result["revision"] == 2 and len(result["rules"]) == 1
    assert not result["mailbox_effects"]
    assert store.search(ctx, SearchRequest(query="Melron"))[0]["classification"]["effects"] == {
        "category": "promotion",
        "canonical_mailbox": "review_delete",
    }
    assert store.evidence(ctx, hit["evidence_id"]) == original
    assert control.rollback(human, 2, 1)["revision"] == 3
    assert (
        store.search(ctx, SearchRequest(query="Melron"))[0]["classification"]["effects"]["category"]
        == "investment"
    )
    assert control.rollback(human, 3, 0)["revision"] == 4
    assert control.list(ctx)["rules"] == []
    # A lost-response retry cannot silently undo the rollback.
    assert control.activate(human, receipt["id"])["revision"] == 1
    assert control.list(ctx)["revision"] == 4
    with pytest.raises(Conflict):
        control.rollback(human, 3, 0)


@pytest.mark.parametrize(
    "sender,matched",
    [
        ("a@example.invalid", True),
        ("Alice <a@EXAMPLE.INVALID>", True),
        ("a@sub.example.invalid", False),
        ("a@evil-example.invalid", False),
        ("example.invalid", False),
        ("a@example.invalid,b@evil.invalid", False),
        ("a@example.invalid.evil", False),
        ("a@example.invalid.", False),
    ],
)
def test_exact_sender_domain(sender, matched):
    entry = {"proposal_id": str(uuid4()), "version": 2, "payload": rule().model_dump()}
    result = classify([entry], 1, sender)
    assert bool(result["effects"]) is matched
    assert result["virtual_only"]


@pytest.mark.parametrize(
    "domain",
    [
        ".",
        ".example",
        "example..invalid",
        "-example.invalid",
        "example-.invalid",
        "x" * 64 + ".invalid",
        "example.invalid.",
    ],
)
def test_reject_malformed_rule_domains(domain):
    with pytest.raises(ValidationError):
        rule(domain=domain)


@pytest.mark.parametrize("bad", ["bad\x00text", "bad\ud800text"])
def test_rule_and_proposal_text_reject_database_poison(bad):
    with pytest.raises(ValidationError):
        rule(category=bad)
    with pytest.raises(ValidationError):
        ProposalRequest(payload=rule(), reason=bad, source="test")
