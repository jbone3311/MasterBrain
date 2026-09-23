# ADR-051 — Reviewed, evidence-linked KnowledgeCore assertions

Status: accepted for the additive prototype tranche on 2026-09-22.

## Decision

KnowledgeCore stores entities, aliases, relationships, claims, events, projects and
commitments as tenant-isolated append-only assertions. Each publication is explicitly
reviewed by a human, cites one or more immutable DataCore evidence records, carries a
bounded source quote, confidence, observation time and optional validity interval.

Objects may supersede an earlier object of the same kind, but never update or erase it.
Corrections link a target to a replacement and preserve the reason and evidence.
Contradictory claims can coexist and remain independently cited. A source statement is
not elevated to verified truth merely because it was extracted or reviewed.

A separate immutable search projection provides deterministic lexical discovery over
knowledge objects. The stable object remains the typed table row; the projection is
rebuildable from it. Knowledge changes have their own monotonic cursor feed rather than
being forced into source-version changes.

## Authority and safety

- Publication requires `knowledge.review` and a human client at the API boundary.
- Search, object reads and changes use separate read scopes.
- All tables use forced RLS and explicit runtime grants.
- IDs are opaque and tenant-scoped. Cross-tenant entity, project and evidence links
  fail through composite foreign keys or pre-publication verification.
- Replays return the original result; key reuse with different content conflicts.
- No model is authorized to publish automatically in this tranche.

## Verification and rollback

Tests cover every object kind, idempotency, supersession, corrections, conflicting
claims, temporal validation, evidence requirements, scope/human enforcement, RLS,
immutability, concurrency, lexical retrieval, change cursors and populated restore.
Rollback disables publication/read routes without deleting assertions or evidence.
