# ADR-248 — First-party synthetic XLSX source selection and approval

Status: implemented on an open PR; private extraction, actual-browser and hosted gates remain open.

## Decision

Extend the existing first-party Email search/evidence screen, not a separate privileged backend. An inspected message displays an XLSX selection button only for a deferred `.xlsx` attachment with the exact OpenXML spreadsheet media type and a reason eligible for the isolated extractor. Selecting shows the original Email evidence ID, attachment receipt, safe filename, MIME SHA-256, part path and part SHA-256. Selection does **not** approve anything. The owner must click a separate button to call ADR-247's source-attached approval API; the server checks the exact current synthetic occurrence, owner and pinned processor. On success, the `xapp_` ID is placed in ADR-246's result-inspection field, but result inspection and publication do not start automatically.

The browser validates the closed approval response, displays false mailbox/publication effects, uses one idempotency key for explicit uncertain retries, and discards in-flight responses after account, search or credential changes. Evidence and responses render as text, not HTML. Clearing the session also clears the selected source and approval ID. The browser holds no worker scope, never fetches workbook bytes and never performs extraction, publication, source effects or financial certification.

## Acceptance and next gate

DOM tests cover evidence selection without a request, explicit approval without worker calls, same-key uncertain retry, account invalidation, stale credential response and result-input changes during an in-flight request; the static asset test checks the first-party selection slot. ADR-247 separately proves the real API on disposable PostgreSQL. Next add the isolated exact-approval worker command, run a complete synthetic source → approval → actual pinned-image extraction → human review → separate publication → retrieval drill, and obtain actual-browser/accessibility, full PostgreSQL, hosted and independent review gates before merging or using live mail. FOS-Master remains unchanged.
