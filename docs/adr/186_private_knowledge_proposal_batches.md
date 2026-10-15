# ADR-186 — Private source-stated Knowledge proposal batches

Status: accepted for synthetic/disposable implementation only. This does not
define the Librarian Markdown grammar, admit inferred claims, approve a live
source, or change FOS-Master.

## Context

ADR-051 publishes only explicit human-reviewed Knowledge assertions. ADR-169
requires imported/model suggestions to remain private proposals until each
row is selected and reviewed. The statement-specific ADR-172 ledger is not a
general KnowledgeCore queue. A fictional 40-row import needs a durable,
replayable holding area and one atomic review action, without making staged
rows searchable or treating a batch as blanket approval.

## Decision

- Accept a bounded batch of 1–50 closed, source-stated assertion payloads from
  an authenticated human holding `knowledge.review`. Payloads omit `reviewed`;
  the server validates them against the existing typed assertion schemas only
  by temporarily adding that field in memory. It stores canonical JSON and a
  SHA-256 digest in separate immutable, tenant-RLS/tenant-login-fenced proposal
  tables, never in reviewed search or change tables. No file path, model output,
  raw source bytes or provider credential is accepted.
- Every proposed assertion has one or more same-tenant DataCore evidence IDs,
  a bounded source quote appearing exactly in at least one linked normalized
  document, and current, active, nonexcluded evidence at stage time. The human
  preview and review recheck the same source/evidence/quote basis under current
  source grants. During the review transaction, row locks on each direct
  evidence source item and source keep its current-version pointer and active
  status stable through publication. An excluded or revoked basis is not
  disclosed or approved. This lock does not freeze external provider state or
  concurrently edited exclusion policy, and does not change direct publication.
- The preview requires a human reviewer with `knowledge.review` and
  `brain.content.read`; it returns only one exact batch, ordered and bounded.
  No assistant or ordinary Knowledge search/dossier/changes route can read the
  proposal table. It labels all rows unreviewed and untrusted.
- One human `knowledge.review` request explicitly decides every row as approve
  or reject, with a reason for each rejection and the exact batch digest. The
  entire decision is one transaction: approved rows use the existing typed
  KnowledgeCore publication path, reviewer ID, evidence links, search/change
  projection and idempotency receipts; rejected rows get only an immutable
  decision receipt. Any validation or insert failure rolls back *all* rows.
  Actor-scoped UUID request keys and per-proposal decision uniqueness make
  exact replay stable and conflicting re-review fail closed. A proposal is
  never auto-approved by its author, a parser, a model or batch membership.
- The first implementation covers source-stated assertions only. Inference
  proposals without direct quotes require ADR-177's typed basis/derivation
  model and cannot be smuggled into this queue. A later Markdown importer may
  stage through a separate, least-privilege worker path only after its sanitized
  grammar and exclusion/basis contract are accepted.

## Verification and rollback

Use fictional Email/FileOS evidence and disposable PostgreSQL only. Stage 40
rows and prove zero reviewed rows; approve 38/reject two in one transaction;
test exact replay, conflicting decisions, stale/excluded evidence, wrong
source/tenant, malformed quotes, model/assistant refusal, no proposal leakage
through Knowledge reads, failed-row all-or-nothing rollback, direct SQL/RLS/
mutation/TRUNCATE refusal, and populated restore. Keep full CI, strict runtime,
and donor parity gates green. Rollback disables the routes and retains immutable
proposals/decisions for audit; do not delete or reinterpret existing assertions.
