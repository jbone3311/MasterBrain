# ADR-232 — Retained Email XLSX derivation through shared DataCore

Status: implemented as a nonpublishing, synthetic-only proof on an open branch.

## Decision

Reuse DataCore's pinned, isolated `bounded_xlsx_v1` document extractor for one
exact retained Email attachment. The private proof verifies the parent MIME
SHA-256 and size, MIME part path, occurrence-specific attachment SHA-256,
declared spreadsheet type and `.xlsx` name, then invokes the same restricted
document processor used by FileOS. It accepts only a complete extracted result
whose text exactly matches the supplied normalized text and digest. The return
value contains identities, processor version and bounded counts, never source
text or spreadsheet values. Two emails with identical attachment bytes retain
distinct parent identities.

Uncached formulas, malformed packages, incomplete/empty results, changed parent
MIME or attachment bytes, and wrong type/name refuse the proof. The extractor
does not evaluate formulas or macros; its existing limits and deferral policies
are unchanged. The MIME selector runs only in this private operator primitive,
never in a public request path; actual spreadsheet parsing stays in the
restricted document worker. A future operational command must re-read the
retained MIME through an account-authorized source path and recheck the final
account/currentness/grant state before recording any receipt.

## Evidence and next gate

Fictional tests run the real bounded XLSX child logic on authored bytes and
exercise the pinned Docker caller through an isolated fake transport. These
tests are not actual-image execution. No database receipt, Email document
bridge, search/index publication, source freshness, live provider, OCR, cell
locator or financial truth is conferred. ADR-233 pins the donor table/behavior
gaps. Next: an independently approved XLSX extraction and occurrence-specific
Email document bridge, then a tenant-fenced review-bound digest receipt and
private command, followed by actual immutable-image, hosted and independent-
restore gates. The FOS-Master donor stays unchanged.
