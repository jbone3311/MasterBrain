# ADR-027 — Audited retry of current held evidence

Accepted for the local prototype, 2026-09-20. Implements independent recovery in
EB-004, not bulk reindexing, scanner clearance, or a production deployment.

A human owner with `email.review` and `email.evidence.read` may request a retry
of one quarantine receipt, naming the currently deployed parser version. The
receipt UUID and parser version are the natural idempotency key. One immutable
attempt is retained per pair, including failures. A different parser needs a
version bump and a new explicit request; email and model content cannot request it.

Read and hash-check retained bounded MIME; parse outside a database transaction.
Before publishing, acquire the same tenant/account advisory lock as ingestion
and revalidate the receipt against the latest quarantined provider event. A newer
provider update, deletion or inventory reconciliation invalidates publication.
Replayed completed requests return their historical outcome, explicitly not a
claim about current message state. Recheck membership on both transactions.

Successful recovery atomically appends evidence/attachment receipts, changes the
current projection and status, records the attempt and audits the operation.
Failure preserves quarantine and records a fixed content-free outcome. Neither
path advances cursors, manufactures provider events, changes raw bytes, erases
history, executes attachments, calls models, or writes to a mailbox.

Migration 0008 permits separate immutable message versions for the same raw hash
under different parsers. Search must match the current projection's parser, so
historical attachments cannot leak into current results. New quarantine receipts
retain source thread/mailbox/keyword metadata; legacy receipts cannot reconstruct
that metadata and publish it as unknown, never inferred from stale projections.

Rollback: disable the recovery route and stop workers before changing binaries.
Keep migration 0008 and all history; pre-0008 binaries are incompatible with the
new uniqueness key and must not run. Roll forward or perform an explicitly
authorized restore. Historical citation reads remain stable. Undoing recovery
and reprocessing already-ready messages are separate future workflows.

Required tests: actual PostgreSQL transactions/RLS, same-key concurrency, parser
failure, hash mismatch, deleted/superseded receipt, injected mid-parse provider
change, transaction rollback, old citations and current-only attachment search,
scope/human denial, scrubbed API errors, and restore of attempt records.

References: [evidence architecture](../ARCHITECTURE.md),
[PostgreSQL transaction isolation](https://www.postgresql.org/docs/17/transaction-iso.html),
[quarantine contract](../API_MCP_SPEC.md).
