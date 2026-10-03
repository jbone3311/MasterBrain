# ADR-150 — Explicit source focus for current search and Ask

Status: accepted for the read-only Brain API and first-party workspace.

## Context

The current Brain API can search Email, FileOS/archive derivatives and reviewed
KnowledgeCore together. The first-party Ask screen does not let an owner narrow
one question to Email or files. Client-side hiding would still fetch unneeded
source excerpts, and an empty result would not distinguish "not searched" from
"searched with no match." A language model must not infer or expand access.

## Decision

- Add an optional closed `source_focus` request value to current grouped search
  and extractive Ask: `all` (default), `email`, or `fileos`. The caller chooses
  it explicitly; text in a question or retrieved evidence never changes it.
- `email` searches only current bridged Email message, attachment and approved
  document layers. `fileos` searches only active FileOS plus current published
  archive text, document and image layers. Reviewed KnowledgeCore is searched
  only for `all`, because its evidence links can span both source kinds. The
  response keeps all layer keys for compatibility but leaves unsearched layers
  empty and reports the focus in coverage. An empty unsearched layer is not a
  "no match" assertion.
- Keep existing scopes, enrollment, transaction-time revocation, current-state
  predicates, evidence/content drill-down, answer quote recheck, limits and
  partial-coverage warning. A narrowed focus is never a new grant. The
  provider-neutral reference client and `/brain` send the same value.
- Do not make an automatic source classifier, stored conversation, model
  synthesis, action route, current FileOS v2 switch or FOS-Master change.

## Verification and rollback

Cover invalid focus refusal, zero calls to excluded layers, bounded default
compatibility, real PostgreSQL Email/FileOS known answers, source-scoped
assistant denial, browser display of unsearched groups and external-client/API
parity. Run full CI, strict runtime and populated restore before merging.
Rollback is code-only: older clients omit the field and continue using `all`;
an older server refuses a newer focused request rather than silently widening
it. No schema or evidence is rewritten.
