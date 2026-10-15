# ADR-236 — Reviewed FileOS XLSX row-layout replay receipt

Status: implemented for synthetic-only, worker-initiated use on an open PR.
ADR-237 subsequently adds a private, exact-source operator command.

## Decision

Bind ADR-235's confined XLSX table observation to exactly one existing human
source-tier review, current FileOS source version and normalized document.
The worker must hold `brain.document.publish`, pass the source grant, and use
the same immutable image as the document's normalizer. Before processing it
checks the review quote and full indexed body digest. It then reacquires the
file without following symlinks and reruns the isolated table worker. In a
second database transaction it locks the source item and source rows, checks
the entire basis again, and reauthenticates through an optional controller
callback before inserting an immutable tenant-fenced receipt.

The receipt contains source/text SHA-256s, root binding, image-bound versions,
sheet/row/cell counts, and a row-layout SHA-256. It contains no cell values,
quotes, filenames, source root path, or financial conclusions. An exact replay
is idempotent; a different result for the same review fails. Database guards
reject stale source versions, changed review/document/source bindings, absent
actor context, and attempts to update, delete or truncate the receipt.

## Evidence and limits

Disposable PostgreSQL tests prove ordinary and repeat replay, worker/source
scope refusal, late authorization denial, changed bytes, a current-version
race and database immutability. The table worker's physical row coordinates
are observed by the pinned child, not independently authenticated by the
existing indexed-text digest. This receipt is not a source-freshness
certificate after the transaction, cell-level citation, searchable table,
financial approval, proof against a compromised worker, or FileOS cutover.
ADR-237 subsequently adds the private operator command. Actual-image
execution, hosted CI and independent restore remain separate gates. No live
root or FOS-Master change is authorized.
