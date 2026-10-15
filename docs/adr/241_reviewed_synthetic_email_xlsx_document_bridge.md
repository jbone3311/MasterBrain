# ADR-241 — Reviewed synthetic Email XLSX document bridge

Status: implemented on an open PR with fictional PostgreSQL coverage; actual
immutable-image execution, hosted exact-head CI and independent populated
restore remain required before merge. No live Email source is accepted.

ADR-242 supersedes the single-principal authorization described below: human
review and worker publication are now separate, because ingest/publication
scopes are worker-only. The DataCore document and receipt design remains.

## Decision

Publish one complete, immutable ADR-240 extraction result only after a human
principal explicitly supplies its exact text SHA-256, sheet count and cell
count. As corrected by ADR-242, the reviewer needs Email review/evidence
scopes; a separate worker needs DataCore ingest/document publication scopes.
The service rechecks the unexpired ADR-239 approval,
current synthetic account, approving and reviewing owners, current parent and
attachment occurrences, active source and exclusion state under the account
transition lock and source-row locks. A changed digest or count refuses before
publication. This is explicit digest-bound human authorization, **not** a
claim that a UI has shown every cell or that any financial fact is true.

The existing attachment occurrence evidence remains the citation target. A
second normalized document, deterministic chunks, source evidence input,
processor/policy/result/chunker provenance and one change event are written
atomically. A separate immutable, tenant-fenced receipt binds the approval,
result, human review, worker actor, idempotency key, occurrence, document, digest and code
revision. The SQL insert guard independently verifies the current basis,
text/body digest and actual chunk count. It does not reuse PDF jobs or PDF
bridge receipts, copy MIME into the Brain database, move an Email item, or
write to FOS-Master.

Generic Brain search, evidence expansion/content and the current Email-family
search include the derivative only while its exact synthetic parent,
attachment, source and exclusion state remain current. Source-scoped reads
filter before results are returned. Published text is untrusted extracted
content; its citation identifies the attachment occurrence, **not a verified
cell coordinate**, owner interest, investment amount or source-tier decision.

## Acceptance and limits

Fictional disposable-PostgreSQL tests cover publication, exact replay,
provenance and chunks, no-result/nonhuman/digest-mismatch refusal, SQL
forgery and immutability, source-scope denial and post-publication source
pause. Historical populated-upgrade and protected-table checks must pass.
The explicit actual-image suite now contains an approval → isolated extraction
→ reviewed publication → Email-family search case, but Docker is unavailable
locally; collection is not execution. A first-party review screen, cell-level
row citation, table index, complete donor workbook parity and live Fastmail
acceptance are separate next gates. Do not cut over FileOS or retire FOS-Master.
