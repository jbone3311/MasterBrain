# ADR-238 — Exact retained Email XLSX row-layout proof

Status: synthetic-only, nonpublishing primitive on an open PR.

## Decision

For one exact retained MIME parent and XLSX part, rerun the separate bounded
table worker in the same pinned immutable image as the existing document
normalizer. Bind its ordered sheet/physical-row/value projection to the
already-known normalized text SHA-256, and return only a layout digest,
counts, processor version and parent/part identities. The parent MIME digest
and part path retain occurrence identity when workbook bytes recur in another
email. A blank physical row can therefore change the layout digest without
changing the indexed text digest. This is not a claim about headers, formulas,
finances or completeness beyond the worker's bounded textual-cell scope.

Reuse ADR-232's exact parent/part selector and ADR-234's isolated table worker.
The proof refuses changed MIME, part bytes/path, normalizer image, indexed text,
malformed workbooks and unsupported formulas. No cells, email content or
financial assertions leave the primitive. It reads supplied retained bytes
only, with no database or provider access.

## Acceptance and next gate

Fictional tests exercise exact, repeated-occurrence, blank-row, wrong-basis,
formula and malformed-package cases through the fake Docker transport. The
explicit document-container suite collects a chained actual-image test for
both the Email text and physical-row proofs; it has not run locally. This adds
no Email XLSX approval, review receipt, indexing, API, live-mail permission or
FileOS cutover.
Next: design an independently reviewed XLSX extraction/occurrence-specific
Email bridge; then tenant-fenced receipt and private exact-account command.
Actual-image, hosted exact-head and independent-restore gates are still open.
