# ADR-064 — Current-only search for bridged Email evidence

Status: accepted and verified for the additive prototype tranche on 2026-09-22.
Revision `743fb9e` passed hosted
[CI 35737349912](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35737349912)
and [restore 35737349873](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35737349873).

## Decision

Add `DataCoreStore.search_current_email` and the additive
`POST /v1/brain/email-search` route. The read requires `brain.search`, uses the same
bounded lexical request/result shape as other Brain evidence searches and returns
only Email documents that satisfy both current-state boundaries at query time:

- the shared source item points at the searched DataCore version; and
- the bridge receipt's legacy message version still matches the Email message's raw
  digest and parser version and the message is neither deleted nor quarantined.

The query joins through the immutable bridge receipt; it does not infer identity from
content or locators. Results remain compact, untrusted excerpts with opaque evidence,
document, source and locator IDs. The response labels visibility
`current_bridged_email`.

## Compatibility and limits

The legacy `/v1/search` Email path remains authoritative and unchanged. This route
contains only explicitly bridged messages, so absence may mean not bridged rather than
not present. A newly updated Email message disappears until its new immutable version
is explicitly bridged. Deletion or quarantine hides it immediately without deleting
retained shared evidence; retained `/v1/brain/search` remains historical.

This decision adds no automatic bridge, attachment migration, merged scoring,
KnowledgeCore synthesis, mailbox/provider authority or global search redirect.

## Acceptance

PostgreSQL tests must prove initial visibility, update-before-rebridge disappearance,
new-version visibility, delete/quarantine hiding, replay, RLS and opaque identity
parity. API tests must prove scope, bounds, method selection and visibility labeling.
All existing Email and FileOS behavior must remain green.

## Rollback

Remove callers from the additive route. No source, evidence, receipt or legacy Email
row is mutated by search.
