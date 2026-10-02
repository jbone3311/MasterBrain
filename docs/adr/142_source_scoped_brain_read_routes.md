# ADR-142 — Source-scoped Brain read-route expansion

Status: accepted for synthetic implementation, 2026-10-02.

## Context

ADR-130/132/133 allow enrolled assistants to use current grouped search,
evidence/content expansion, changes and current coverage. Other Brain read
routes deliberately deny assistants, even when their requested source is
enrolled. That fail-closed posture prevents leaks but leaves the public read API
inconsistent for an approved external client. Issue #88 remains open.

## Decision

Extend assistant access to the existing read-only Brain routes whose source
semantics can be enforced without changing their human behavior:

- Retained DataCore search filters source IDs in SQL **before** ranking and
  `LIMIT`.
- Aggregate current FileOS, Email and Email-family searches use their existing
  source-filtered SQL paths.
- FileOS source freshness, inventory, rebuild preview, index status and active
  search require the exact source ID to be enrolled. A hidden source and an
  unknown source both return not found, before disclosing status, counts,
  cursors, or hits.

The API dependency admits only assistants with a nonempty source enrollment;
the DataCore operation enforces it again within the transaction. An OIDC
identity's binding revision and source set are rechecked when that transaction
opens, so removal invalidates a saved principal before a read. Synthetic
bootstrap grants remain static and are not represented as dynamically
revocable. Existing human owner reads retain their current tenant-wide
behavior. No write, original-byte, provider or filesystem authority is added.

Unified Brain and direct KnowledgeCore routes stay denied to assistants until
their assertion, correction, linked-object and change-feed source semantics
are separately reviewed. Legacy Email routes remain outside this decision.

## Verification and rollback

Use one tenant with nonempty FileOS and Email sources, a second tenant,
source-limited bootstrap and OIDC assistants, and a revoked OIDC grant. Assert
no cross-source result, no hidden-source count/status/cursor, filtering before
limit, and transaction-time refusal of a saved principal after revocation.
Run full Python/Node, migration/deployment, documentation, strict-runtime and
restore gates. Roll back the API/library change if necessary; this ADR adds no
schema, source effect or irreversible data migration. Keep issue #88 open for
Knowledge/legacy routes, hosted issuer enrollment and derived-cache acceptance.
