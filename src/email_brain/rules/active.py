"""Read-time, virtual-only classifications; never mutate provider or evidence state."""

from __future__ import annotations

from email.utils import parseaddr
from typing import Any

import psycopg

from email_brain.rules.engine import Predicate, Rule, RuleEngine
from email_brain.schemas import RulePayload


def current_rules(conn: psycopg.Connection[dict[str, Any]]) -> dict[str, Any]:
    return conn.execute(
        "SELECT * FROM rule_revisions ORDER BY revision DESC LIMIT 1"
    ).fetchone() or {"revision": 0, "rules": []}


def classify(rules: list[dict[str, Any]], revision: int, sender: str) -> dict[str, Any]:
    # Malformed/ambiguous sender headers fail closed; domain matching is not sender auth.
    # Runtime capability is checked at package startup. TypeError is a defect,
    # never an ordinary malformed sender or a successful empty classification.
    try:
        address = parseaddr(sender, strict=True)[1]
    except ValueError:
        address = ""
    domain = address.rsplit("@", 1)[1].lower() if address.count("@") == 1 else ""
    compiled = []
    for entry in rules:
        payload = RulePayload.model_validate(entry["payload"])
        compiled.append(
            Rule(
                rule_id=entry["proposal_id"],
                version=entry["version"],
                priority=0,
                all_of=(Predicate("sender_domain", frozenset({payload.sender_domain})),),
                effects={
                    "category": payload.category,
                    "canonical_mailbox": payload.canonical_mailbox,
                },
                source="human_activated",
            )
        )
    result = RuleEngine().evaluate(compiled, {"sender_domain": domain})
    return {
        "rules_revision": revision,
        "effects": dict(result.effects),
        "matched_rule_versions": list(result.matched_rule_versions),
        "virtual_only": True,
    }
