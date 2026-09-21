# Approved PDF attachment processing

Implemented synthetic API/library slice, 2026-09-21; verification belongs to the
exact-commit [build receipt](BUILD_RECEIPT.md). [ADR-035](adr/035_approved_document_processing.md)
and migration 0012 extend the [restricted PDF worker](PDF_WORKER.md). No live mail,
scanner, cloud deployment, UI controls or document operator CLI is implied.

## What it does

A ready email can retain a deferred PDF without being quarantined. Its owner can
approve that exact attachment for restricted processing. The result is saved
separately, including page text and explicit partial/deferred/failed outcomes.
Authorized search can find the PDF text and return its own immutable citation.
The original email body, attachment receipt, raw bytes, cursor and citation do not
change. Completed means a result was saved, not necessarily successful extraction.

## Approval and execution

An operator configures `document_processor_version` on `create_app`; default `None`
disables new approvals. It must be `sandbox-pdf-v1-<64-character image hash>`.
There is no HTTP image/command/socket configuration or worker-execute route.

| Method/path | Contract |
|---|---|
| `GET /v1/accounts/{account_id}/documents` | Evidence scope; capability/policy/version; worker liveness remains unknown |
| `POST /v1/accounts/{account_id}/attachments/{receipt_id}/jobs` | Human owner with review AND evidence scopes; UUID `Idempotency-Key`; closed body below |
| `GET /v1/accounts/{account_id}/documents/jobs` | Evidence scope; history limit 1–50 and same-account UUID `after` |
| `GET /v1/accounts/{account_id}/documents/jobs/{job_id}` | Evidence scope; bounded public status, no lease/actor credentials |
| `POST /v1/accounts/{account_id}/documents/jobs/{job_id}/cancel` | Human review/evidence; terminal result is idempotent |
| `GET /v1/documents/{document_id}` | Evidence scope; historical result, provenance and at most 40 page excerpts of 2,000 characters |

Approval body: `expected_processor_version` must equal the configured version;
`policy_version` must explicitly equal `synthetic-unscanned-pdf-v1`. Receipts are
the attachment UUIDs returned by the existing message-evidence endpoint. Unknown,
foreign or ineligible sources return 404; disabled/changed channel or reused intent
returns 409; malformed requests return 422. All routes retain bootstrap owner/RLS
checks and content-free diagnostics. No raw download, password or arbitrary upload.

Only active accounts with no provider enrollment and a `synthetic:` secret reference
qualify. These labels are an operator boundary, not a classifier proving content
is fictional. Never mark real accounts synthetic to bypass live/scanner gates.

A separately trusted worker invokes
`DocumentJobs(store, processor.processor_version).run_once(worker, account, processor)`
with `DockerPdfProcessor` and a worker principal carrying `email.document.process`.
The old `email.process` scope and `process-jobs` CLI still authorize MIME recovery
only. Production use requires restricted execution, not an in-process PDF helper.

Jobs retain a one-hour approval, exact source event/receipt/processor/policy, at
most three claims and a 120-second lease. Infrastructure retries wait 60 then 120
seconds; callers schedule polling, the library does not sleep. The account has a
100-unfinished-job cap. Parent validation, current owners/source and database-clock
fences guard disclosure and publication. No SQL transaction spans PDF execution.
An already-running child may finish after cancellation; its result cannot publish.

## Search and evidence

Set `include_documents: true` on `POST /v1/search` to include document results.
It defaults false for existing clients/UI, independently of `include_attachments`.
Results are bounded by the same final search limit. Document hits include
`result_type: document`, `document_id`, original `evidence_id`/`attachment_id`,
processor/policy/revision, status/reason, `scanner_status: unscanned` and citation
`emailbrain://document/{document_id}`. The new document endpoint resolves it;
the old message endpoint does not masquerade as the source of extracted PDF text.

FTS sees only the newest extraction revision for a current, nondeleted,
nonquarantined message version. A newer failed/deferred result suppresses earlier
text as current, but old citations remain readable to authorized owners. Repeated
approval of an existing receipt/processor/policy uses its immutable result after
fresh fences; it does not promote an older revision over a newer one.

Text-only page excerpts carry offsets, truncation flags and excerpt hashes. Text
and sender claims remain untrusted; no PDF is rendered or declared safe. Scanner
status does not change when extraction succeeds. Office, OCR and archives remain
outside this channel.

## Deployment, operations and rollback

Migration 0012 adds `document_jobs` and `document_extractions`, composite ownership,
forced RLS, protected state/identity and immutable receipts/results. Apply reviewed
migration and runtime grants before enabling the updated API/worker. No delete or
authority-table UPDATE grant is added. The receipt protection also forbids admin
UPDATE/DELETE outside an explicitly designed future retention procedure.

Disable new approvals by removing the configured channel; cancel pending jobs and
stop document workers separately. Existing results remain searchable on opt-in.
Use forward repair or tested restore, not destructive downgrade. Restore includes
completed/cancelled/pending document grants, immutable text/provenance, FTS and
tenant denial; original expiry is never refreshed. Inspect pending consent before
restarting workers. Fixed `document.job_*` and evidence-read audit events contain
references/outcomes, not source text or parser exceptions.

## Verification and remaining work

Tests cover known text absent-before/present-after, unchanged source state,
idempotency/cache, bounded retries, racing claims/cancel, revoked membership/account,
enrollment/source changes, expired consent/leases, processor/output substitution,
atomic audit failure, historical/current revisions, foreign resources, API schema
denials and SQL immutability. The explicit PDF container suite additionally runs
the actual restricted worker through PostgreSQL and authorized search.

UI approval/result rendering, operator CLI/supervision, scanner policy, supported
live identity/enrollment/storage and broader real-world quality/soak remain open.
Do not infer their completion from this source-to-search acceptance.
