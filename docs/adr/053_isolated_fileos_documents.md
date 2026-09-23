# ADR-053 — Isolated, source-bound FileOS PDF and Office extraction

Status: accepted and verified for the additive prototype tranche on 2026-09-22.

## Decision

DataCore may extract bounded PDF, DOCX and XLSX source versions only through a
dedicated immutable container image and a closed pipe contract. The FileOS adapter
reopens each source under its authorized root, refuses symlinks/escapes, checks size
and stat stability, and verifies the snapshot SHA-256 before any bytes enter the
processor. The child response is treated as untrusted and rebound to the exact source
version, locator, digest, media type and size before publication.

The container runs as UID 10001 with no network, mounts, capabilities, logging or
writable root; it has fixed memory/CPU/PID limits, `no-new-privileges`, an inspected
entrypoint/command and bounded stdin/stdout. The ordinary API image still excludes
PDF and Office readers.

PDF processing refuses encryption, actions, annotations, forms, embedded files,
collections, excess pages/streams/text and image-only content requiring OCR. OOXML
processing preflights member counts, paths, duplicates, symlinks, encryption, macros,
external relationships, DTD/entities, expansion size and compression ratio before
opening the package. DOCX paragraphs/tables and XLSX cached values are bounded; no
formula, macro, relationship or source action is executed.

Every file receives an explicit `extracted`, `deferred`, `changed` or `failed`
outcome. Only complete extracted text is published to shared immutable evidence,
provenance, chunks and lexical search. One processor failure does not prevent sibling
files from being accounted for.

## Provenance and parity

The behavior reference is FOS-Master commit
`218d5caec2f20b9047fd3eb8e027dc671acf0c15`, especially
`_SYSTEM/tools/doc_extract.py` and `_SYSTEM/tests/test_doc_extract.py`. The donor
source/test hashes already recorded in the tool inventory remain unchanged. The live
parity harness compares DOCX and XLSX extracted tokens and workbook sheet counts in
addition to the existing 3,000-file/hash/text corpus. PDF policy reuses the repository's
already container-tested `pypdf==6.19.0` safety lessons; it does not claim pdfplumber
table parity or OCR parity.

## Verification and rollback

Offline tests use real synthetic PDF/DOCX/XLSX bytes and adversarial corrupt,
external-link, macro and high-expansion OOXML packages. Parent tests prove that source
bytes are withheld until container isolation is inspected, source substitution is
rejected, and owned cleanup is mandatory. Hosted CI must build the dedicated image,
run all formats through the real container and publish them through PostgreSQL to
shared search without modifying their source files.

Revision `a6488c6` passed that gate in
[CI 35711403192](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35711403192):
five real-container cases covered all three formats, hostile/source-binding behavior
and PostgreSQL publication. The populated restore passed separately in
[run 35711403138](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35711403138).

Rollback removes the processor image/configuration and constructs `FileOSAdapter`
without a document processor. PDF/DOCX/XLSX then return the earlier unsupported
outcome; existing source observations and published evidence remain immutable.
