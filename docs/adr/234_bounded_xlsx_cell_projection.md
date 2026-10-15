# ADR-234 — Bounded, addressable XLSX cell projection

Status: implemented as an isolated, nonpublishing DataCore worker on an open PR.

## Decision

Add a separate `sandbox-xlsx-tables-v1` pipe contract instead of changing
`bounded_xlsx_v1` text extraction or its existing indexed output. The new
worker accepts the same source-bound, exact-SHA document request, performs
the existing bounded OOXML preflight and projects nonblank physical rows with
1-based sheet index and row number, positional cell values and explicit sheet
visibility. A caller can derive a cell coordinate from row and column index;
no row is asserted to be a true semantic header. Blank cells in a represented
row remain positional. Hidden sheets are labeled, not silently dropped.

This is **textual cell coverage only**. A formula anywhere defers the whole
workbook with no rows, even if a cached value exists. Invalid, encrypted,
oversize, over-complex, empty and overlong input fails or defers without
partial tables. The fixed-profile Docker caller validates the entire child
response, source identity, output size, ordering, bounds and statuses. It uses
the approved immutable image only, with the same no-network/read-only
isolation checks as the existing document processor. A pinned image is part
of the trust base: a malicious but validly-shaped response from a compromised
image is not independently proven by JSON validation.

## Donor baseline and limits

The ADR-233 pinned FOS-Master replay matches ordinary header-candidate and
row values, including a 1,000-row tail. DataCore also retains physical row
numbers that the donor table output drops. Known differences remain for
formula caches, configured partial row truncation, encrypted classification,
`.xlsm`, and unrepresented workbook features. The donor is unchanged.

The new projection is not persisted, indexed, exposed by Brain API, linked to
an Email attachment, or approved as financial evidence. Local synthetic tests
exercise the worker logic and simulated fixed-profile Docker caller; the
actual-image check is added to the explicit document-container suite but has
not run locally because Docker is unavailable. Hosted CI and independent
restore remain acceptance gates. Next add a reviewed policy/receipt for
structured cells and an occurrence-specific Email XLSX extraction/bridge.
