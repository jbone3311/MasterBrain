# ADR-221 — Defer XLSX formulas and overlong cells

Status: implemented with fictional, unscanned DataCore documents on an open
PR; hosted exact-head checks remain open.

## Context

The restricted XLSX worker read cached values only. A formula with no cached
value became `None`, so a sheet containing source text plus such a formula
could be labeled extracted while silently omitting the formula. It also
truncated each cell's text after 1,000 characters, again returning an
extracted result. Neither outcome is safe as a source-text basis for a
financial statement.

## Decision

Read XLSX cells with formulas visible, never evaluate formulas or trust a
cached result as current. If any formula cell appears, return
`deferred/unsupported_features` with no published text. If a normalized cell
exceeds 1,000 characters, return `deferred/text_limit` with no published text
instead of truncating it. Ordinary bounded non-formula cells retain their
existing projection. The byte-bound and ZIP safety checks remain in force.

This conservative boundary may defer a workbook whose formulas have valid
caches; it avoids silently converting unknown computation state into a
fact. It does not claim that charts, drawings, macros, comments, displayed
number formats, hidden material or every spreadsheet feature is captured.
No donor code or live source is changed.

## Acceptance and next gate

Author fictional workbooks with a mixed text/uncached-formula row and a
mixed text/1,001-character row. Both must pass the closed worker contract as
deferred with empty text; their source-version extraction must also defer
without changing source bytes. Existing bounded XLSX, PDF and DOCX cases
must still extract. Run local and hosted gates before merge.

Next establish a versioned, independently checked sheet/cell/feature coverage
receipt and reviewed policy for formulas, cached results and displayed
financial values. A deferred or extracted XLSX worker result is not issuer
authentication, a financial claim or FileOS replacement parity.
