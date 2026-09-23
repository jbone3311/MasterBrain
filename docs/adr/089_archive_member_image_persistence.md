# ADR-089 — Persist one successful archive-image OCR derivative

Status: accepted and implemented through `63b478d`.

## Context

ADR-088 proves exact one-member archive-to-image OCR composition but intentionally
returns only memory. The next smallest useful step is durable evidence for one explicit
successful result. Reusing a text or PDF/Office receipt would erase image engine and
dimension provenance; adding a selector or command would combine policy with storage
before the storage transaction is proven.

## Decision

Add a separate append-only, forced-RLS image receipt and a narrow DataCore publication
method. Admit only a complete nonempty `bounded_image_ocr_v1` result from an exact 5A
target. Reconstruct and lock the current parent/inventory/member before writing. Reuse
the deterministic archive-child source identity, store OCR text as a normalized
document, and bind both worker contracts plus image metadata in receipt and provenance.

Keep empty OCR in memory for now. Preserve legacy manifest media hints and record the
canonical format as derivative metadata. Activate no current-search join until a later
decision can define freshness and ranking explicitly.

## Alternatives rejected

- Reuse archive text receipts: they cannot bind image engine/format/dimensions.
- Reuse document receipts: PDF/Office policy and image OCR outcomes are different.
- Persist blank OCR as a document: the current normalized-document/chunk model is for
  searchable content; an empty observation needs a separately justified ledger.
- Add a selector, command or batch now: first prove transaction fencing and replay.
- Rewrite sealed manifest media hints: historical inventory is immutable evidence.

## Rollback

Remove the publication wrapper/method and forward migration before production use.
The 5A in-memory composition, isolated image worker, archive manifests, text/document
derivatives and all existing retrieval remain unchanged. Applied append-only evidence
is retained unless a separately authorized data-retention operation is designed.

## Implementation

Implemented in design `16d452a`, runtime `760a644` and correction `63b478d`. Hosted
[CI 35833506295](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35833506295)
and [restore 35833506298](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35833506298)
are green. Private command, current search, preview, batch and fan-out remain separate
decisions.
