# ADR-076 — Persist archive inventory before child evidence

Status: implemented and accepted in runtime `03dbb98` with correction `08ccb68`.

## Context

ADR-075 proves bounded member identities inside an isolated worker, but the result is
ephemeral. Persisting child evidence now would conflate inventory with byte retrieval,
text extraction and search publication. It would also make rollback and provenance
ambiguous because the first worker intentionally returns no member bytes.

## Decision

Add an append-only tenant-isolated archive inventory ledger bound to one existing,
current FileOS source version and one immutable processor version. Store the canonical
accepted result digest, ordered hash-only members, ordered skips and aggregate counts.
Accept only complete or partial bounded results. Refused or failed outcomes, including
bombs and duplicate safe identities, publish no database rows.

Seal the child ledgers with deferred database checks, use forced RLS and the existing
immutable trigger, and record actor-scoped exact-replay receipts. A unique source
version/processor pair makes deterministic drift a conflict rather than a second truth.

## Non-goals

No member bytes, child source versions/evidence, normalized text, chunks, search,
change events, API, CLI, scheduling, FileOS effects or cutover are authorized. A later
ADR must define a one-member hash-bound read and its extraction/publication policy.

## Acceptance and rollback

The SQL and store method require real PostgreSQL replay/concurrency/RLS/immutability/
atomicity tests and populated restore proof. Existing searches must remain unchanged.
Rollback stops use of the additive ledger; FOS-Master and current shared paths remain
untouched.

The gates passed in hosted CI 35783950712 and populated restore 35783950915.
