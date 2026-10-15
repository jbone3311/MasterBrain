# ADR-220 — Defer mixed text/image PDF extraction

Status: implemented for fictional, unscanned DataCore documents on an open PR;
hosted exact-head checks remain open.

## Context

The bounded DataCore PDF worker previously concatenated text-bearing pages
and returned `bounded_pdf_v1` even if another page yielded no text. A mixed
text/scanned statement could therefore publish an apparently successful
document while omitting a page. This is especially unsafe for financial
documents: a page count alone does not show whether each page contributed.

## Decision

Keep the existing PDF worker and source-binding contract, but return a
`deferred/pages_without_text` outcome with no published text whenever a PDF
contains both text-bearing and no-text pages. Fully no-text PDFs remain
`deferred/empty_document`; fully text-bearing PDFs remain extracted. The
page count is retained for private review. This is deliberately conservative:
a truly blank page also defers until a later, separately reviewed page-coverage
proof can distinguish it from an image-only page. It changes no donor code and
does not claim that text-bearing pages were extracted completely or faithfully.

## Acceptance and next gate

An authored two-page PDF with a text page and an image-only page must pass the
closed pipe contract but defer with empty public text and a count of two.
Existing single-page PDF, DOCX and XLSX extraction must remain unchanged.
Run local repository gates and hosted exact-head validation before merge.

Next, design an independently checked per-page PDF coverage receipt, including
image/OCR detection, source-byte binding and failure behavior; then address
spreadsheet silent truncation/cached-formula coverage. Neither this deferral
nor a successful PDF worker result attests issuer authenticity, financial
truth, live-source readiness or FileOS replacement parity.
