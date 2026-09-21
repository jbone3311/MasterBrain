"""Human activation of sampled sender rules; append-only history, no mailbox effects."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from email_brain.auth import Principal
from email_brain.domain.models import TenantContext
from email_brain.rules.active import classify, current_rules
from email_brain.schemas import RulePayload
from email_brain.store import AccessDenied, Conflict, NotFound, Store, digest


class RuleControl:
    def __init__(self, store: Store) -> None:
        self.store = store

    def human(self, principal: Principal) -> TenantContext:
        if principal.client_kind != "human":
            raise AccessDenied("human required")
        self.store.require(principal.context, "email.review")
        self.store.require(principal.context, "email.search")
        return principal.context

    @staticmethod
    def lock(conn: psycopg.Connection[dict[str, Any]], ctx: TenantContext) -> None:
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", ("rules:" + str(ctx.tenant_id),)
        )

    @staticmethod
    def proposal(
        conn: psycopg.Connection[dict[str, Any]], identifier: UUID, version: int
    ) -> dict[str, Any]:
        row = conn.execute(
            "SELECT * FROM proposals WHERE id=%s FOR SHARE", (identifier,)
        ).fetchone()
        if row is None:
            raise NotFound()
        if row["kind"] != "rule" or row["status"] != "approved" or row["version"] != version:
            raise Conflict("approved rule at exact version required")
        try:
            RulePayload.model_validate(row["payload"])
        except ValueError:
            raise Conflict("proposal no longer satisfies the bounded rule schema") from None
        return row

    @staticmethod
    def candidate(current: dict[str, Any], proposal: dict[str, Any]) -> list[dict[str, Any]]:
        domain = proposal["payload"]["sender_domain"]
        rules = [r for r in current["rules"] if r["payload"]["sender_domain"] != domain]
        rules.append(
            {
                "proposal_id": str(proposal["id"]),
                "version": proposal["version"],
                "payload": proposal["payload"],
            }
        )
        if len(rules) > 100:
            raise Conflict("active rule capacity reached")
        return sorted(rules, key=lambda r: r["payload"]["sender_domain"])

    def list(self, ctx: TenantContext) -> dict[str, Any]:
        self.store.require(ctx, "email.search")
        with self.store.transaction(ctx) as conn:
            result = current_rules(conn)
            self.store.audit(conn, ctx, "rules.list", "rules")
            return {**result, "mailbox_effects": False}

    def simulate(
        self, principal: Principal, proposal_id: UUID, expected_version: int
    ) -> dict[str, Any]:
        ctx = self.human(principal)
        with self.store.transaction(ctx) as conn:
            self.lock(conn, ctx)
            proposal = self.proposal(conn, proposal_id, expected_version)
            current = current_rules(conn)
            candidate = self.candidate(current, proposal)
            rows = conn.execute(
                "SELECT m.id,CASE WHEN v.snapshot->'sender_rule_eligible' = 'true'::jsonb "
                "THEN m.sender ELSE '' END AS sender FROM messages m "
                "JOIN message_versions v ON v.tenant_id=m.tenant_id AND v.message_id=m.id "
                "AND v.raw_sha256=m.raw_sha256 AND v.parser_version=m.parser_version "
                "WHERE NOT m.deleted AND NOT m.quarantined ORDER BY m.id LIMIT 50"
            ).fetchall()
            sample = [
                {
                    "message_id": str(row["id"]),
                    "before": classify(current["rules"], current["revision"], row["sender"])[
                        "effects"
                    ],
                    "after": classify(candidate, current["revision"] + 1, row["sender"])["effects"],
                }
                for row in rows
            ]
            result = conn.execute(
                "INSERT INTO rule_simulations(tenant_id,actor_id,proposal_id,proposal_version,"
                "proposal_hash,base_revision,sample) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                (
                    ctx.tenant_id,
                    ctx.actor_id,
                    proposal_id,
                    expected_version,
                    digest(proposal["payload"]),
                    current["revision"],
                    Jsonb(sample),
                ),
            ).fetchone()
            assert result is not None
            self.store.audit(conn, ctx, "rules.simulated", "rule_simulation", str(result["id"]))
            return {**result, "coverage": "bounded_sample", "mailbox_effects": False}

    def activate(self, principal: Principal, simulation_id: UUID) -> dict[str, Any]:
        ctx = self.human(principal)
        with self.store.transaction(ctx) as conn:
            self.lock(conn, ctx)
            receipt = conn.execute(
                "SELECT *,expires_at>now() AS fresh FROM rule_simulations "
                "WHERE id=%s AND actor_id=%s",
                (simulation_id, ctx.actor_id),
            ).fetchone()
            if receipt is None:
                raise NotFound()
            existing = conn.execute(
                "SELECT * FROM rule_revisions WHERE simulation_id=%s", (simulation_id,)
            ).fetchone()
            if existing:
                self.store.audit(
                    conn, ctx, "rules.activation_replayed", "rule_simulation", str(simulation_id)
                )
                return {**existing, "mailbox_effects": False, "replayed": True}
            current = current_rules(conn)
            if not receipt["fresh"] or receipt["base_revision"] != current["revision"]:
                raise Conflict("simulation expired or rules changed")
            proposal = self.proposal(conn, receipt["proposal_id"], receipt["proposal_version"])
            if digest(proposal["payload"]) != receipt["proposal_hash"]:
                raise Conflict("proposal changed")
            rules = self.candidate(current, proposal)
            result = conn.execute(
                "INSERT INTO rule_revisions(tenant_id,revision,actor_id,rules,simulation_id) "
                "VALUES (%s,%s,%s,%s,%s) RETURNING *",
                (ctx.tenant_id, current["revision"] + 1, ctx.actor_id, Jsonb(rules), simulation_id),
            ).fetchone()
            assert result is not None
            self.store.audit(conn, ctx, "rules.activated", "rule_revision", str(result["revision"]))
            return {**result, "mailbox_effects": False, "replayed": False}

    def rollback(
        self, principal: Principal, expected_revision: int, target_revision: int
    ) -> dict[str, Any]:
        ctx = self.human(principal)
        if (
            type(expected_revision) is not int
            or type(target_revision) is not int
            or not (0 <= target_revision < expected_revision)
        ):
            raise Conflict("rollback requires an earlier revision")
        with self.store.transaction(ctx) as conn:
            self.lock(conn, ctx)
            current = current_rules(conn)
            if current["revision"] != expected_revision:
                raise Conflict("rules changed")
            prior = (
                {"rules": []}
                if target_revision == 0
                else conn.execute(
                    "SELECT rules FROM rule_revisions WHERE revision=%s", (target_revision,)
                ).fetchone()
            )
            if prior is None:
                raise NotFound()
            result = conn.execute(
                "INSERT INTO rule_revisions(tenant_id,revision,actor_id,rules,restored_from) "
                "VALUES (%s,%s,%s,%s,%s) RETURNING *",
                (
                    ctx.tenant_id,
                    expected_revision + 1,
                    ctx.actor_id,
                    Jsonb(prior["rules"]),
                    target_revision,
                ),
            ).fetchone()
            assert result is not None
            self.store.audit(
                conn, ctx, "rules.rolled_back", "rule_revision", str(result["revision"])
            )
            return {**result, "mailbox_effects": False}
