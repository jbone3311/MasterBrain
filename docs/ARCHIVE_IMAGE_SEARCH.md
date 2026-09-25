# Current archive-image OCR search

Status: synthetic implementation under [ADR-107](adr/107_current_archive_image_search.md).
This read path exposes only explicitly published, nonempty OCR derivatives. It does
not run OCR, enumerate archive members or change source files.

## Current-evidence fence

`DataCoreStore.search_current_archive_images` requires `brain.search` and a
nonblank, NUL-free query of at most 500 characters. Each result must join one
append-only image receipt to its exact normalized document, evidence and chunk,
the sealed inventory/member, and a parent FileOS item still pointing at that
inventory's source version. The child item must still point at the receipt's
version; child hash, size and legacy media hint must match the sealed member.
The member must not be a container. JPEG/PNG/TIFF/BMP/GIF/WebP suffixes must agree
with canonical and detected image format in the receipt. A changed parent or
inconsistent receipt drops the hit without deleting retained history.

## API and privacy

`POST /v1/brain/current-search` includes independently bounded/ranked
`archive_images` results, `archive_image_limit` (1–20), and coverage
`explicitly_published_current_archive_images_only`. The result carries only
opaque IDs/child locator, a bounded excerpt and within-layer rank. Full text
requires the separate content scope. It does not return the archive member's
virtual path, raw image, OCR worker details, dimensions or EXIF. The grouped read
still reports `independent_layer_reads`, not a single atomic snapshot or globally
comparable rank.

## Tests and remaining gates

Known-answer PostgreSQL tests cover publication/replay, all eight supported image
suffix mappings, wrong tenant, independent layers, invalid limits and parent
replacement. Separate donor-worker parity verifies actual image bytes; the suffix
query tests exercise sealed receipt metadata. API tests cover closed request and
response shape. The tenant-leading receipt index is migration 0036. Restricted
worker, populated restore and donor parity remain required CI/release gates;
live-source shadow, automatic fan-out, hosted security and FOS-Master cutover are
not accepted by this read path.
