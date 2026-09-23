# ADR-084 — Keep current archive documents in their own search layer

Status: accepted design; implementation pending.

## Context

Checkpoint 4V publishes exact archive-contained PDF/Office derivatives after an active
FileOS generation may already be sealed. The existing archive-text current layer is
receipt-specific and cannot prove the second document-worker boundary or distinguish
document formats. Generic retained search does not prove that the parent archive is
still current.

## Decision

Add a separate forced-RLS current archive-document query joined through the immutable
document receipt, sealed inventory/member, current parent FileOS item and exact child
version/evidence/document. Require exact PDF/DOCX/XLSX suffix, media and container
classification. Add only a tenant-leading receipt index.

Expose results as an independently limited and ranked `archive_documents` layer in
`/v1/brain/current-search`. Preserve the archive-text layer, active FileOS generations
and retained-history search unchanged. Continue to return opaque child locators and
require existing evidence/content scopes for drill-down.

## Alternatives rejected

- Merge document receipts into `archive_members`: hides distinct processor/policy
  coverage and implies comparable ranks.
- Mutate or rebuild the active FileOS generation: violates sealed plans and grants
  scheduling authority.
- Trust the child current pointer: leaves stale derivatives visible after parent
  replacement.
- Search all retained document receipts: mislabels historical evidence as current.

## Rollback

Remove the read method, request/response layer and lookup index. Checkpoint-4V
receipts, evidence, normalized documents, retained search and source state remain
unchanged.

