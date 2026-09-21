# ADR-035 — Approved PDF attachments, durable results and search

Accepted 2026-09-21 for the authorized synthetic/local/CI build. No real-mail,
hosted processing, malware-safety or new mailbox authority is granted.

## Decision

Add a separate document-job channel and immutable document extractions. Do not
reuse quarantine approvals: an otherwise ready message can have a deferred PDF.
Its existing body, attachment receipts, evidence, provider events and cursors must
not change when its document is processed or fails.

The owner explicitly approves one current PDF receipt, exact processor image
version and fixed `synthetic-unscanned-pdf-v1` policy. Approval requires human
review and evidence scopes. The initial channel accepts only active unenrolled
synthetic accounts; scanner/live policy is a separate future decision. No upload,
password, command, image selection or execution endpoint is exposed to clients.

Store a one-hour approval, actor-bound idempotency key and current source event
identity. Workers need the new worker-only `email.document.process` scope, not the
existing MIME-processing scope. Claim at most one job, use a 120-second lease,
three-attempt limit and bounded delayed infrastructure retries. Explicit cancel,
expired consent, revoked owners/account, replaced source/event or lease loss must
fence publication. Processing occurs outside SQL transactions. Recheck immediately
before child disclosure and in the atomic publication transaction. Use the existing
account advisory lock and narrow owner-lock helper; no authority-table UPDATE grant.

The worker loads the source through the approved owner's narrow internal evidence
path, verifies hashes and invokes ADR-034's restricted processor. The parent again
validates the closed result contract and processor identity. Deterministic extracted,
partial, deferred and failed outcomes are immutable results; infrastructure failure
is not cached as document failure. Preserve the unscanned designation throughout.

Migration 0012 adds tenant/account composite ownership, forced RLS, append-only
result and receipt protection, immutable approval identity and protected job
transitions. Results are keyed by receipt/processor/policy; sequential per-receipt
revisions distinguish newer processors. Completion references the exact source,
processor and policy result and commits with its audit record. Cached results still
require fresh valid consent/ownership/source fences.

Search optionally includes current-source latest document revisions using FTS.
Choose the latest revision before filtering outcome, so a newer deferral never
silently exposes older extraction text as current. Give each result its own stable
evidence URI and bounded, untrusted page excerpts. Historical result reads retain
their immutable source identity; provider deletion hides current search, not retained
evidence. No raw attachment download or change to existing body citations.

## Acceptance and limits

Prove a PDF-only known marker absent before approval and present after the actual
restricted worker/SQL path, while body/evidence/cursor/receipts remain unchanged.
Test foreign accounts/tenants/scopes, cancellation, expiry, revocation, source
changes, lease replacement, process failure/retry, cached results, processor drift,
publication rollback, SQL immutability, current-versus-historical search and restore.
API approvals/history/cancellation/results are separate from worker execution.
UI and operator CLI integration must be labeled pending until implemented/tested.

No new dependency, remote model, SMTP, provider action, cloud resource, scanner or
Factory runtime mutation. Default API/MIME image still excludes pypdf.

## Operations and rollback

Coordinate migration, runtime grants, API and worker deployment. Disabling the
configured channel prevents new approvals; explicitly cancel outstanding approvals
and stop its workers to revoke pending work. Preserve results/receipts and use
forward repair or tested restore; do not delete evidence or down-migrate. Restore
SQL/objects/keys together, retain original consent expiry, and review pending jobs
before starting workers. Audit fixed job outcomes without mail or exception text.

References: [ADR-034](034_source_bound_pdf_worker.md),
[recovery contract](../RECOVERY_JOBS.md), [data model](../DATA_MODEL.md),
[security](../SECURITY.md), [test plan](../TESTING_AND_EVALS.md).
