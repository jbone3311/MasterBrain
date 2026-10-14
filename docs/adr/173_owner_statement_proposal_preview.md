# ADR-173 — Owner-only preview of unreviewed statement proposals

Status: accepted for synthetic/disposable testing. This is a read-only
inspection surface, not approval, verified investment data, live-source
enrollment, assistant access, or FileOS cutover.

## Context

ADR-172 records exact-decimal rows privately, but a human cannot inspect the
stored extraction through the same API boundary as other MasterBrain evidence.
Publishing rows as `knowledge_claims` just to make them visible would erase the
distinction between proposed extraction and reviewed fact. Returning a whole
statement or every row in one request would also defeat progressive access.

## Decision

- Add `GET /v1/knowledge/statement-proposals/{proposal_id}` for a human owner
  with both `knowledge.read` and `brain.content.read`. Assistants and workers are
  denied even when they hold those scopes. The route is read-only and never
  creates, edits, approves or publishes a claim.
- Look up the exact immutable proposal under tenant RLS and the caller's current
  source grants. Rejoin its document, evidence, source version, item and source;
  refuse a stale/inactive source, changed text/source digest, or mismatched
  proposal basis. Unknown or ungranted IDs both return not found.
- Recompute the full ordered row digest before disclosing any page. Return at
  most 25 rows, each with its original document character offsets and a quote
  capped at 300 characters plus an explicit truncation bit. The next-page
  cursor is the immutable row ordinal. The response is no-store and its audit
  event contains only opaque IDs.
- Label every row `proposed_extraction` and the entire response untrusted and
  unreviewed. `reconciled` means only donor-tolerance arithmetic; USD is a
  recipe assumption. No aggregation, inferred holding, account total,
  financial recommendation, or source effect is returned.
- The disposable fictional browser trial may create one proposal from its own
  published FileOS fixture. Its trial-only locator route discloses only the
  random proposal ID to that trial owner's temporary credential; the normal
  source-rechecked API still authorizes the content. The page fetches and
  displays it only after an explicit click, rendering quotes as inert text.
  This does not create a production proposal-list endpoint.

## Verification and rollback

Disposable PostgreSQL/API tests cover Email and FileOS, exact quotes and
decimals, pagination, both scopes, human-only access, source-grant denial,
current-version refusal and absence of reviewed claims. The full repository,
strict-runtime and populated-restore gates remain release checks. No test uses
personal data. Rollback removes the route and reader while retaining the
immutable proposal ledger and audit history.
The trial integration adds a second-tenant denial and browser tests for
click-only reads, inert rendering and rejection of malformed responses.
