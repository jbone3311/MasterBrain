# ADR-247 — Source-attached synthetic Email XLSX approval API

Status: implemented on an open PR; isolated extraction remains a separate worker step.

## Decision

Expose the existing ADR-239 exact-occurrence approval service through a human-only `POST /v1/accounts/{account_id}/attachments/{receipt_id}/xlsx-approvals` route. It requires `email.review` plus the service's `email.evidence.read`, an `Idempotency-Key` UUID, current account ownership and the existing database-checked synthetic XLSX source basis. The client supplies no processor version or workbook bytes. `serve --xlsx-document-processor-version` explicitly pins the XLSX image digest independently of the existing PDF-only `--document-processor-version`; without it the route returns 503 before writing an approval. An invalid pin prevents server startup. The response contains the stable `xapp_` ID, changed/replay flag, and explicit false mailbox/publication effects. No worker operation is reachable from the human API.

This route only authorizes a one-hour isolated extraction attempt for one current synthetic attachment. It does not verify the worker image ran, inspect contents, certify cells, create a DataCore document, or permit live Fastmail. The owner still needs the separately scoped isolated extraction workflow and ADR-246 review screen. FOS-Master remains unchanged.

## Verification and next gate

A real disposable PostgreSQL test exercises first approval, idempotent replay, missing key, unknown receipt, missing XLSX pin and assistant denial. The existing ADR-239 service and SQL tests cover stale source, wrong account, immutability, cross-tenant access and synthetic-only eligibility. ADR-248 adds the first-party source-attached approval affordance and ADR-249 the private exact-approval extraction command; immutable-image and hosted checks remain before claiming an end-to-end workflow.
