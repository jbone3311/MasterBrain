# ADR-240 — Isolated result for one approved synthetic Email XLSX

Status: private worker and protected result implemented on an open PR;
DataCore document bridge, Brain API search and live mail are not implemented.

## Decision

Consume only one unexpired ADR-239 human approval for an exact currently
bridged synthetic Email attachment. The private worker requires
`email.document.process` and `email.evidence.read`, checks source grants and
current parent/attachment/account state, and reads only the retained MIME
identified by the approval. It verifies the MIME hash and size, exact MIME
part path/hash and XLSX type/name before invoking the same pinned restricted
DataCore document image used for FileOS. It accepts only a complete
`bounded_xlsx_v1` result with unscanned status and bounded sheet/cell/text
counts. Formula-dependent, incomplete, changed or unavailable input leaves no
result row.

After extraction, the worker rechecks the approval and current source under
the account transition lock and source-row locks, rechecks owner/worker
authority, and seals one immutable result containing the extracted text,
its SHA-256, exact parent/part identities, pinned processor and counts. The
SQL insert guard independently requires the unexpired current approval and
source; a database CHECK recomputes the stored text digest. The public return
contains only the approval ID, digest, counts and no-publication flags. The
result table is tenant-fenced and denies UPDATE, DELETE and TRUNCATE.

This is a trusted-worker observation, not cryptographic proof that a database
administrator or compromised runtime actually invoked the image. The existing
PDF jobs and bridges are unchanged. No XLSX text enters Brain normalized
documents, chunks, index or API in this tranche; no source file or mailbox
effect occurs. FOS-Master remains untouched.

## Acceptance and next gate

Fictional disposable-PostgreSQL tests cover exact extraction/replay, wrong
image, lost final authorization, paused source, uncached formula, immutable
rows and a forged text digest under a second legitimate approval. Historical
migration, protected-truncation and populated-upgrade checks pass. The Docker
pipe is fake in these tests; actual immutable-image execution is still open.
Next implement an occurrence-specific reviewed DataCore document bridge with
provenance and chunks, then bounded retrieval/citation. Exact-head hosted CI
and independent populated restore remain required before merge. Live
Fastmail remains disabled by the approval contract.
