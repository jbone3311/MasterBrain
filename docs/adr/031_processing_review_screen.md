# ADR-031 — Persistent processing history and owner controls

## Decision

Make ADR-030 approvals accessible from the existing owner screen and reloadable
from PostgreSQL, rather than relying on a job ID held in a browser tab. Add bounded
account-scoped job history, explicit approval and cancellation controls, and manual
status refresh. No automatic approval, polling daemon, mailbox write, model call,
raw download, parser selection or controller privilege is introduced.

## API and storage

`GET /v1/accounts/{account_id}/processing/jobs?limit=50&after={job_uuid}` requires
current owner membership and `email.evidence.read`. Return at most 50 jobs using
the existing public job projection, plus `next_after`, `limit` and
`mailbox_effects: false`. Order by immutable `(created_at DESC,id DESC)`; resolve
the cursor in the same tenant/account before paging. Missing/foreign account or
anchor returns 404, invalid UUID/limit returns 422, absent scope returns 403.
This is live keyset pagination, not a frozen export: refresh the first page to see
new approvals and updated states. No status filter over mutable state is added.

Migration 0011 adds an account/time/ID history index without changing approvals,
job transitions, scopes or grants. Bound direct library limits as well as HTTP.
Record content-free `recovery.jobs_read` audit events. Register this fixed route
before the dynamic job-ID route so `jobs` is never parsed as an ID.

## Owner interaction

An explicit processing refresh loads configured capabilities and durable history
for the selected account. Disabled channels show status/history but no approval
button; worker presence remains unknown, not inferred from configuration. Current
held-message controls may approve isolated parsing only after a matching capability
version has been loaded. Explain the one-hour durable approval, cancellation and
the fact that completed processing can still leave binary attachments unread.

An approval click binds the displayed account, receipt, full parser version,
session and view generation. Allocate one UUID idempotency key for that request
and retain it for retries after an uncertain network result while that control's
context is unchanged. Never silently reapprove under a new key or a new image.
Disable double clicks while a request is pending. Refresh the durable list to
reconcile uncertainty; no mutation retries run automatically.

Pending jobs offer explicit cancellation. Completed/cancelled/expired/failed/stale/
revoked jobs display a fixed explanation rather than actionable source text.
Cancellation may lose a race to already committed completion: display the returned
terminal state, never claim cancellation merely because the HTTP request succeeded.

Validate bounded response shapes, identifiers, state/outcome agreement, parser
versions and account binding before rendering controls or reporting success.
Render text only; never HTML or arbitrary object/error dumps. On credential changes,
disconnect, account changes or superseding refreshes, clear private content and
invalidate all old callbacks and responses. No local/session browser storage.

## Verification and rollback

Test SQL paging order/ties/limits/foreign anchors, fixed-route dispatch, scopes,
no raw/lease disclosure, and history after process recreation. Independently test
UI explicit clicks, image binding, uncertain-result idempotency, double clicks,
cancellation races, all fixed states, malformed responses, pagination and session/
account/same-account refresh races. Preserve existing UI/security tests.
Use a synthetic browser preview for visual/interaction acceptance when available;
DOM contract tests alone do not prove accessibility or live-service readiness.

Rollback the UI/API while retaining the index and all approvals. In-flight approved
jobs remain governed by ADR-030 expiry/cancel/revocation; removing a button does not
revoke a grant. Hosted identity, controller supervision, binary extraction and
disposable-provider acceptance remain separate gates.

Sources: [PostgreSQL indexes](https://www.postgresql.org/docs/17/indexes-multicolumn.html),
[FastAPI route order](https://fastapi.tiangolo.com/tutorial/path-params/#order-matters).
