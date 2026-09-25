# ADR-068 — Current-only Email-family search

Status: accepted and verified in revision `9b427e1`.

## Context

`POST /v1/brain/email-search` intentionally returns only explicitly bridged message
documents that remain current in both legacy Email and shared DataCore state. ADR-065
and ADR-066 now also publish attachment text and approved PDF derivatives, but the
generic retained-history search is the only shared read that can find them. Mixing
message, attachment and derivative ranks into one flat limit would hide result classes
and make migration parity difficult to measure.

## Decision

Add `DataCoreStore.search_current_email_family` and a separate
`POST /v1/brain/email-family-search` endpoint. The request has independent bounded
limits for message, attachment-text and approved-document results. The response keeps
three named layers and declares ranking as within-layer only; it does not compare ranks
across different representations.

Every layer must rejoin the immutable bridge receipts to the legacy parent message and
require its raw/parser version to remain current, visible and not quarantined/deleted.
Shared parent and child source-item current pointers must still match their bridged
versions. The attachment layer accepts only the ADR-065 receipt's own normalized
document; the document layer accepts only an ADR-066 receipt, preserving result kind
even though both cite the same attachment evidence.

The endpoint requires only `brain.search`, returns bounded untrusted excerpts and opaque
identities, and exposes no filenames, addresses, provider IDs, MIME bytes or approval
details. The existing message-only endpoint and generic retained-history search remain
unchanged compatibility surfaces.

## Acceptance and rollback

Synthetic PostgreSQL tests must prove all three layers, duplicate attachment occurrence
preservation, independent limits, no cross-layer rank claim, tenant isolation and
immediate disappearance after parent update, deletion or quarantine while retained
history remains queryable. API tests must prove scope, closed bounds and response labels.
All existing suites and populated restore must remain green. Rollback removes only the
new endpoint/method; immutable evidence and existing reads are unchanged.

This gate passed hosted
[CI 35749176559](https://github.com/jbone3311/MasterBrain/actions/runs/35749176559)
and [restore 35749176556](https://github.com/jbone3311/MasterBrain/actions/runs/35749176556)
on 2026-09-22 Pacific. CI and deployment each passed 2,440 Python tests; PostgreSQL
17 restore verified 65 tables and 232 rows. See `docs/BUILD_RECEIPT.md` for complete
measured totals.
