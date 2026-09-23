# Archive-member image OCR persistence

Status: checkpoint 5B implemented and accepted through correction revision `63b478d`.

## Purpose

Publish the nonempty OCR text from one explicitly selected, current archive image
member after the accepted 5A two-worker composition succeeds. This is an append-only
DataCore derivative with exact provenance. It is not image selection, a command,
search activation, a batch or archive-wide processing.

## Admission

The caller supplies the existing forced-RLS `ArchiveMemberTargetRecord`, the complete
5A `ExtractionResult`, a deployed code revision and a caller-owned idempotency key.
Publication requires all of the following:

- the extraction version and locator equal the deterministic target identity;
- status is `extracted`, reason is `bounded_image_ocr_v1`, error is absent and text is
  nonempty, NUL-free and within the existing normalized-document byte cap;
- suffix, canonical format and detected format agree for JPEG/PNG/TIFF/BMP/GIF/WebP;
- image processor identity is nonempty and bounded, dimensions are positive and no
  more than 25 megapixels, frame count is exactly one, mode is bounded, and truncation
  is boolean; and
- the selected member is no larger than 8 MiB and is not an archive container.

Valid blank OCR remains a successful 5A in-memory result but is not published in this
tranche. Deferred and failed results never enter a transaction.

## Identity and storage

Reuse the deterministic archive-child item, version and source-bound evidence identity
already shared by text and document derivatives. Preserve the sealed manifest media
hint in the child source version; record the canonical image format in metadata rather
than rewriting old inventories. A normalized document and deterministic chunks contain
only bounded OCR text. Raw member bytes, decoded pixels and EXIF are never stored.

A new append-only `brain_archive_member_image_receipts` table records tenant, actor,
key, exact inventory/member/parent identities, derived evidence/document identities,
immutable image processor, canonical/detected format, dimensions, mode, one-frame
count, truncation, chunk count, code revision and canonical request digest. It has
forced RLS, immutable rows and foreign keys to the sealed member, parent evidence,
child source version/evidence and normalized document.

Provenance uses transform `archive_member_image_ocr`, binds both existing sandbox
contracts, inventory and image processor versions, canonical image format, OCR policy,
chunking configuration and code revision, and names the parent archive evidence plus
inventory as inputs. The receipt is distinct from text and PDF/Office receipts.

## Transaction fence and replay

Under a per-member advisory lock, first resolve an existing key. Exact replay returns
the original identities without duplicate evidence, documents, chunks, provenance or
change events; changed input under the same key conflicts. A different key for the
same target/processor may reuse only an identical canonical request.

Before the first write, lock the current source item and reconstruct the inventory and
member from database columns. Require exact equality with the pre-worker target, the
same current parent version and `is_container=false`. Parent replacement, inventory
or member drift, format mismatch, processor drift and key misuse fail atomically.

## Acceptance

- exact JPEG/PNG/TIFF/BMP/GIF/WebP results publish deterministic evidence, document,
  chunks, provenance, change event and image receipt without raw bytes;
- blank, deferred, failed, unsupported, malformed, mismatched and over-limit results
  produce no rows;
- exact retry, equivalent-key replay and concurrent calls converge; changed request
  or key reuse conflicts;
- stale parent, changed inventory/member, container flag and transaction-time races
  fail before any partial write;
- forced RLS, cross-tenant denial, append-only triggers, foreign/check constraints and
  populated logical restore cover the new table;
- retained-history retrieval may see the normalized OCR document, while every current
  archive search remains unchanged until a separate current-query checkpoint; and
- all donor parity, real two-container, PostgreSQL, restore and documentation gates
  remain green.

## Non-goals

No database selector, private/public command, current search, preview, batch, retry-key
generation, scheduling, automatic fan-out, archive recursion, blank-result receipt,
scanner verdict, external vision, raw image/pixel/EXIF retention, source effect,
KnowledgeCore projection or FOS-Master cutover is authorized.

## Accepted evidence

Design revision `16d452a`, runtime revision `760a644` and grant/freshness/provenance
correction `63b478d` passed
[CI 35833506295](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35833506295)
with 2,640 PostgreSQL-backed Python tests and every restricted-container gate. The
independent populated [restore
35833506298](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35833506298)
verified 72 tables and 238 rows with content hashes, forced RLS and identity state
preserved. The first hosted runtime attempt correctly exposed the omitted runtime-table
grant; independent review also moved fresh equivalent-key replay behind the current
fence, kept processor-specific observations out of child source identity, and bound the
image contract/policy explicitly in provenance before acceptance.
