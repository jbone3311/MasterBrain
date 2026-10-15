# ADR-246 — First-party synthetic XLSX result review

Status: implemented on an open PR with DOM, static-route and fictional API-to-UI contract tests. Actual browser/accessibility, immutable-image extraction and hosted exact-head gates remain open.

## Context

ADR-242 exposes human-only bounded inspection and exact-result review routes, but the first-party Email screen had no way to use them. The worker-only publication command must not be moved into the browser. An owner-selected existing synthetic XLSX approval ID is the narrow input for this first screen; creating an extraction approval and running its isolated worker are separate operational steps, not silently implied by result review. ADR-248 later adds explicit source selection/approval to the same page, but still does not run the worker.

## Decision

Add a first-party review section to the Email capability screen. It accepts only a closed `xapp_` ID, fetches text in 16,000-character pages, validates the exact response shape and stable digest/counts/total/source identity across pages, and displays untrusted text with `textContent`. The owner sees the original attachment filename, account, parent Email evidence, part path and part digest. It withholds the review button until every page has been received and the browser's SHA-256 of the concatenated UTF-8 text matches the server's sealed digest. Missing browser digest support, malformed pages, changed identity, credential/account changes and stale responses fail closed. Review is a separate explicit click with an idempotency key retained for uncertain retries. The server rechecks current owner, source and result state; the browser cannot publish or claim worker scopes. It retains no token or result in browser storage and refuses redirects on bearer requests.

The UI cannot certify that every financial cell is correct, that the workbook was scanned, that a human read each page, or that the document was published. It shows the review ID for a separately scoped private worker. It does not enroll live Fastmail or modify mail/files.

## Acceptance and remaining gates

Seven focused DOM cases cover paging, no auto-review/publication, digest mismatch, changed result/source, uncertain retry, credential/account invalidation and inert text. At this ADR's original checkpoint, the first-party Node suite passed 174/174. A static-route test and a fictional PostgreSQL/API-to-UI response contract execute. Hosted exact-head CI, actual browser/accessibility, immutable worker-image execution, a result/worker queue and the separate worker operation remain required before an end-to-end alpha claim. ADR-248 adds explicit source approval, not worker execution.
