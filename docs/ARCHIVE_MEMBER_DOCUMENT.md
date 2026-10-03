# Archive-member PDF and Office derivative contract

Status: checkpoint 4V is implemented in the cumulative synthetic `main` stack;
this does not establish live-source or production acceptance. See the
[current implementation status](IMPLEMENTATION_STATUS.md).

## Purpose

Publish bounded text from one explicitly selected `.pdf`, `.docx` or `.xlsx` member
of one current persisted archive inventory. This composes the proven hash-bound member
reader with the proven isolated document worker; it does not add another document
parser, unpack an archive to disk or authorize inventory-wide processing.

## Two isolated boundaries

1. Forced RLS resolves one exact non-container member of a current archive inventory.
2. The existing archive-member image receives the byte-identical current parent archive
   and releases at most that one member after verifying inventory processor, locator,
   hash, size and parent identity.
3. The privileged parent keeps the returned bytes only in bounded process memory and
   verifies the member hash and size again.
4. The existing document image receives those bytes under the closed
   `sandbox-fileos-document-v1` contract. It has no archive, source mount, network,
   credentials or knowledge of siblings.
5. Only a complete `extracted`, still-`unscanned` PDF/DOCX/XLSX result may enter the
   publication transaction. Raw member bytes are discarded and never persisted.

The member-reader cap and document cap are both 8 MiB. Existing document limits remain
unchanged: 40 PDF pages, 200,000 returned characters, bounded OOXML package expansion,
and the current paragraph/table/sheet/row/column/cell limits. Encryption, active or
external features, embedded recursion, malformed input, image-only PDFs and every
known bound produce a refusal rather than partial publication.

## Identity, persistence and provenance

The selected member reuses the deterministic child item/version/evidence identity
defined by the archive-member text contract. A separate append-only
`brain_archive_member_document_receipts` ledger records the exact document processor
version, document/chunk identity, code revision, request digest and caller key. It does
not overload or rewrite text receipts.

The transaction locks and reconstructs the archive inventory/member/current-parent
record immediately before publication. It rejects any drift from the pre-worker
selection. The normalized document points to the member child evidence. Provenance
names the parent archive evidence and accepted inventory and binds both isolated
contracts, both immutable image-derived processor versions, the format, code revision
and chunking configuration. Source bytes and the FileOS tree remain unchanged.

The first tranche enters retained-history retrieval only. Current archive search must
not include these documents until a later query tranche explicitly joins the new
receipt to the still-current parent and exact sealed member identity.

## Private command

Add `masterbrain fileos archive-document --config ... --inventory-id ...
--member-locator ... --idempotency-key ... [--check]`. The owner-private config binds
both immutable worker image IDs, the absolute Docker binary and authorized root,
private expiring credentials/token and deployed code revision. The worker retains
exactly `brain.source.ingest` and `brain.document.publish`.

Check mode validates closed private configuration, both immutable image bindings,
authentication and the least-privileged database role. It does not query the target,
construct either worker, read source/member bytes or consume the key. Normal execution
reauthenticates before target selection, each isolated boundary, publication and
output. Output contains opaque IDs, format, bounded metadata counts, chunks and replay
state—never locator, path, bytes, text, document properties, Docker details or errors.

## Acceptance

- exact flat/nested ZIP/TAR PDF, DOCX and XLSX fixtures publish complete known text;
- encrypted/active/external/macro/escaping/duplicate/oversized/empty/image-only and
  malformed fixtures publish no evidence, document, chunks or receipt;
- archive-worker and document-worker crash, timeout, malformed output and identity
  substitution each fail closed and remain indistinguishable in ordinary output;
- stale parent, changed member, wrong media/suffix, key reuse and processor/revision
  drift fail before publication; transaction-race tests prove the final fence;
- exact retry and concurrency converge without duplicate evidence or documents;
- check mode proves no DataCore target, worker, source, receipt or key effects;
- source bytes and metadata remain unchanged; no sibling or embedded object is read;
- full PostgreSQL/restore, both real restricted images, donor parity and existing text
  batch/search gates remain green.

Checkpoint 4V is implemented in design revision `ea6fd29`, orchestration `6680218`,
selector/receipt migration `0210ad1` with assertion correction `a4af448`, publication
`4d098fa`, private command `5bb1aa1` and real two-image chain gate `49b8383`. Final-head
[CI 35810970182](https://github.com/jbone3311/MasterBrain/actions/runs/35810970182)
passed 2,582 Python tests and the four-case real chained-image gate; populated
[restore 35810970151](https://github.com/jbone3311/MasterBrain/actions/runs/35810970151)
also passed.

The implemented tranche intentionally remains retained-history-only. Current archive
document search, preview/batch expansion, scheduling and automatic fan-out require
separate checkpoints.

## Non-goals

No batch, preview expansion, discovery, OCR, image extraction, legacy DOC/XLS, embedded
object recursion, scanner verdict, raw-byte retention, public API, scheduler, source
effect, current-search activation or FOS-Master cutover is authorized.
