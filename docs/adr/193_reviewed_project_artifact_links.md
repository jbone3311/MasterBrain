# ADR-193 — Reviewed project-to-artifact evidence links

Status: accepted for synthetic/disposable implementation only. This does not
change FileOS or Email intake, certify a complete dossier, or authorize effects.

## Context

KnowledgeCore can return a reviewed project's events, commitments and people,
but it has no explicit association to a specific Email attachment or FileOS
evidence item. Hash dedupe must not collapse distinct attachment occurrences.
The Librarian export gap (#180) needs source-scoped artifact associations before
it can render a related-files section. A search hit or matching filename is not
a reviewed project link.

## Decision

- Add an append-only reviewed link from one exact project assertion to one
  immutable DataCore evidence identity. The link stores a separate basis
  evidence ID, an exact source quote in that basis's normalized text, a bounded
  relation slug, `asserted` or `retracted`, reviewer, observation and recording
  time. The artifact and basis may be the same item; a parent Email may instead
  provide the quoted basis for its distinct attachment evidence.
- The human write requires `knowledge.review` and `brain.content.read`, a UUID
  idempotency key and full current source grants to the project, artifact and
  basis. Both evidence items must be current, active and nonexcluded; the quote
  is checked in PostgreSQL before insertion. A replay with different content
  conflicts. No model or background classifier creates these links.
- `GET /v1/knowledge/projects/{id}/artifacts` requires `knowledge.search` and
  returns only bounded, cutoff-paged reviewed link metadata and evidence IDs.
  It filters the project and both evidence items under current source grants,
  active/current state and Email exclusion *before* limiting. It exposes no
  source text, path, attachment bytes, quote or automatic file effect. Evidence
  drill-down retains its separate permission. A hidden cursor is not found.
  This first slice returns retained link history, not a computed current roster;
  `retracted` rows remain explicit. A retracted row does not identify or
  automatically negate an earlier row; correction-chain/current-roster
  semantics require a later ADR. No project dossier is silently broadened.
- The table and idempotency receipts are tenant-composite, forced-RLS,
  tenant-login-fenced, immutable and protected from table truncation. Existing
  source/evidence history is never rewritten. Duplicate-content occurrences
  remain separate links because identity is the evidence ID, not the hash.

## Verification and rollback

Use fictional Email and FileOS evidence in disposable PostgreSQL. Test exact
quote binding, source-grant and tenant denial, stale/excluded evidence, wrong
project, pagination before limits, idempotent replay/conflict, SQL mutation and
truncate denial, and restored-populated migration. Full repository and hosted
gates precede merge. Rollback disables the two routes; retain immutable link
and receipt rows for audit. FOS-Master remains unchanged and no live source is
enrolled or read.
