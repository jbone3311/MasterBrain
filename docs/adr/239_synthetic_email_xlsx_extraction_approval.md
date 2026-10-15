# ADR-239 — Separate synthetic Email XLSX extraction approval

Status: human approval boundary implemented on an open PR; extraction and
publication are **not** implemented by this ADR.

## Decision

An Email XLSX must not inherit the PDF-only `document_jobs`,
`document_extractions` or `brain_email_document_bridge_receipts` authorization.
Introduce an immutable, tenant-fenced `brain_email_xlsx_extraction_approvals`
row for a single, currently bridged Email attachment occurrence. The human
approval binds account, parent message version and MIME hash/size, attachment
receipt, MIME part path/hash/size, source event key, exact pinned document
processor version, policy version and one-hour expiry. It stores no MIME,
workbook cells, extracted text, credential or financial assertion. A direct
SQL insert guard checks the current synthetic-only account, ready sync state,
current parent and attachment versions, active Email source, safe XLSX type and
name, and exclusion state. RLS and a restrictive tenant-login fence apply;
UPDATE, DELETE and TRUNCATE are denied.

The narrow service requires a human principal with `email.review` and
`email.evidence.read`, account ownership and allowed source. It locks the
account transition path, checks the current basis, and idempotently records
the approval. Assistants and workers cannot call this approval service.
Existing live Fastmail accounts are not eligible. A valid approval is not
evidence that a worker ran, that a document was published, that contents are
safe, or that a source-tier/financial claim was reviewed.

## Next dependent steps

ADR-240 now adds the separate exact-approval worker and immutable XLSX
extraction result. It loads only the approved retained parent MIME, verifies
currentness, expiry and authorization again, invokes the pinned restricted
document worker, and seals complete text/hash/metadata or refuses. ADR-241
now adds a separate human-authorized, occurrence-specific DataCore text bridge
with provenance, chunks and currentness-gated retrieval. Cell-level
citations, source-tier review and a table receipt remain separate gates.
Actual-image, exact-head hosted CI and independent populated
restore remain required before merge. FOS-Master stays unchanged.

## Acceptance evidence

Fictional loopback PostgreSQL tests cover exact approval/retry, nonhuman and
wrong-account refusal, paused source, direct SQL forged-hash rejection,
immutable rows and no document publication. Historical populated-upgrade,
migration-integrity and protected-truncation suites also pass. No live data
was read or modified.
