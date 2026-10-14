# ADR-172 — Private, evidence-bound statement proposal ledger

Status: accepted for a synthetic/disposable worker-only tranche. It does not
authorize a live source, reviewed holding, Brain API read, or FOS-Master cutover.

## Context

ADR-171 produces exact-decimal, source-neutral candidate rows in memory, but a
worker cannot resume, compare or review them later. Donor line items and run
status remain a separate shape from scalar `knowledge_claims`. MasterBrain needs
an immutable, tenant-scoped proposal ledger before any owner review or investment
dossier. A candidate's own text hash does not prove its source or grant.

## Decision

- An existing `brain.document.publish` worker may select exactly one current
  normalized document by opaque ID. Inside its tenant transaction, the projector
  joins document → evidence → source version/item/source; verifies source kind,
  current version, evidence/source SHA-256 equality, and normalized body SHA-256;
  and parses that stored text. No path, provider token, raw source bytes, arbitrary
  SQL or caller-supplied statement text is accepted.
- Persist one immutable proposal and its ordered grouped rows atomically. IDs and
  row digest are deterministic from document, transform version and exact rows;
  a UUID idempotency receipt is actor-scoped. An exact replay returns the existing
  proposal; key reuse for a different document/transform fails. Incomplete and
  mismatch outcomes remain proposals, never silently promoted or dropped.
- Store exact decimal amounts, source-text offsets, donor commit, transform
  version, source/evidence/document identities, parse coverage codes and
  reconciliation numbers. Source text and quotes are *not duplicated* into the
  proposal tables. The immutable normalized document remains the citation basis.
  `USD` is the single donor recipe's parsing assumption, not independently
  verified currency evidence; `reconciled` is only donor-tolerance arithmetic.
- New tables use forced tenant RLS, the tenant-login restrictive fence,
  tenant-composite FKs, runtime SELECT/INSERT only, immutable update/delete and
  protected TRUNCATE. No migration rewrites existing evidence or reviewed data.
- This is a private library operation, not an HTTP route or assistant tool. A
  later owner review/read design must recheck source grants and exact offsets,
  separate source-stated rows from inferred claims, and require explicit human
  approval before KnowledgeCore publication. A proposal is not a verified
  position, current balance, investment total or financial advice.

## Verification and rollback

Disposable PostgreSQL tests cover same-tenant Email/FileOS documents, exact
decimal rows, replay/conflict, changed body/hash, stale version, missing scope,
cross-tenant RLS, direct SQL basis/row/completion guards, concurrent 1,000-row
replay, direct mutation/TRUNCATE refusal, and absence of reviewed
assertions. A populated logical restore and the full repository gates must pass.
No test uses personal source data. Rollback disables the worker call while
retaining historical proposal rows and receipts for audit; do not drop them.
