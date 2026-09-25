# ADR-107 — Current archive-image OCR search is a separate layer

Status: accepted for synthetic implementation, 2026-09-25. No live-source or
FileOS cutover authority.

## Context

ADR-089 persists OCR for one explicitly selected archive image and ADR-090 adds
its private one-member command. Retained DataCore search can see that derivative,
but it cannot say whether the parent archive is still current. The existing
current archive-text and PDF/Office layers use different receipt and format
contracts. Mixing image ranks into either would obscure provenance and coverage.

## Decision

Add a distinct `archive_images` layer to `/v1/brain/current-search`, with its own
strict 1–20 limit, independent lexical rank and
`explicitly_published_current_archive_images_only` coverage label. A read-only
DataCore query must join the image receipt to its exact derivative, sealed member,
inventory, parent evidence and still-current parent source item. It must also
confirm the child source version is current, matches the sealed member hash/size
and legacy media hint, and that non-container suffix, canonical/detected image
format and receipt identity agree. Return only compact opaque evidence/chunk IDs,
the existing opaque child locator, bounded excerpt and within-layer rank.

Add a tenant-leading image-receipt lookup index without rewriting evidence or
altering active FileOS generations. Preserve retained search and all other
current layers unchanged. Reads remain independently authorized under forced RLS;
the grouped response continues to say `independent_layer_reads`, not an atomic
cross-source snapshot.

The current migration runner creates indexes inside a transaction. Migration 0036
therefore needs a reviewed maintenance/online-index plan before any populated live
deployment; green synthetic upgrades are not lock-duration evidence (issue #9).

## Acceptance and rollback

Prove exact current OCR visibility, independent limits/ranks, no raw bytes/path or
processor metadata, foreign-tenant denial, no text/document-layer bleed, and
parent replacement hiding the old OCR while retained history survives. Exercise
invalid limits, missing/wrong receipt and replay; retain real worker, PostgreSQL,
restore and donor gates. Rollback removes the read method, API layer and index
without deleting published OCR evidence or changing FOS-Master.

This does not select images, run OCR, publish derivatives, mutate generations,
schedule archive work, synthesize an answer, add a source effect or resolve the
separate tenant-context security finding in issue #7.
