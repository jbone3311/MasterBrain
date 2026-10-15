# ADR-225 — Confined FileOS PDF text-layer derivation replay

Status: implemented as a synthetic-only, nonpublishing DataCore primitive on an
open PR. No database receipt, operator command, live root, OCR or financial
claim is authorized by this ADR.

## Context

ADR-218/219 can re-read and attest only built-in FileOS text/Markdown/HTML/CSV
transforms. The FileOS PDF extraction uses a separately restricted document
processor and an immutable image-derived normalizer. A matching source hash
alone cannot establish that a reviewed PDF's published text was reproduced.

## Decision

Add `replay_current_fileos_pdf` for one exact current source-version basis.
The caller supplies the already-authorized root binding, confined locator,
version, byte size/digest, normalized text/digest and exact restricted
processor normalizer. The primitive refuses non-PDF locators, size/identity
mismatches and any processor other than the existing `DockerDocumentProcessor`
with the pinned normalizer. It opens the source through the no-follow confined
reader, rehashes its bytes, runs the existing restricted document-pipe contract,
and requires the exact extracted text, source object, `bounded_pdf_v1` outcome
and bounded nonzero page count. It rechecks the root binding after extraction.
The return contains only digests, byte count, normalizer and page count.

This is a **point-in-time text-layer derivation proof**, not a proof that every
visible glyph or embedded image was understood. The worker already defers any
page without extracted text (ADR-220), but scanned or visually complex PDFs,
OCR, annotations, issuer identity and source authority remain unresolved.
There is no row insert, public route, API write or file effect. The caller must
separately recheck the database source/review/grants under lock before a future
receipt is stored; this primitive by itself is not an attestation.

## Acceptance and next gate

Use fictional PDFs and the existing simulated restricted-pipe harness to prove
exact output, unchanged source, changed bytes, symlink, mismatched hashes,
wrong image identity, image-only deferral and invented-text refusal. Run static
and repository checks. Next implement a tenant-bound review/receipt path with
final authorization and currentness checks, plus actual immutable-image
container and independent restore gates. No FOS-Master cutover follows from
this proof.
