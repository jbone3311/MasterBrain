# ADR-083 — Chain isolated member read and document extraction

Status: accepted design; implementation pending.

## Context

Archive-contained PDF and Office files are currently visible only as hash-manifest
members. The archive worker can safely release one exact bounded member, and the
document worker can safely normalize one source-bound document, but neither contract
alone proves the complete archive-to-document chain or its publication provenance.

## Decision

For one explicit current inventory/member selection, run the existing hash-bound
archive-member reader first and pass only its independently verified in-memory bytes
through the existing closed PDF/DOCX/XLSX document contract. Bind both immutable worker
identities and reauthenticate around both boundaries. Persist no raw bytes.

Use a separate immutable document receipt rather than broadening historical text
receipts. Reuse the deterministic member child evidence, require a transaction-time
parent/member identity fence, and record both contracts and processor versions in
provenance. Initially expose the document only through retained-history retrieval.

## Alternatives rejected

- Extract the archive onto disk: creates a new writable staging/source lifecycle.
- Add PDF/Office libraries to the archive image: merges two hostile-format boundaries
  and weakens independent limits and fault attribution.
- Send the entire parent archive to the document worker: grants it sibling access and
  duplicates archive selection logic.
- Reuse the text receipt without schema distinction: hides the second processor and
  makes policy/query evolution ambiguous.
- Batch or automatically recurse: selection, failure recovery and resource budgets
  need a proven one-member primitive first.

## Rollback

Remove the private command, orchestration and new append-only receipt migration.
Existing archive manifests, one-member reads, text derivatives/batches/search and
ordinary FileOS document processing remain unchanged.
