# Owner processing review screen

[ADR-031](adr/031_processing_review_screen.md) makes the durable approval channel
visible in the local owner interface. It does not enable an unattended worker or
connect a mailbox. The separate controller still needs explicit operator setup.

## Owner workflow

Choose an account, check its import state, then explicitly refresh processing
options/history. The screen reads the server-configured parser and saved jobs.
Configuration is not a worker health signal: worker availability remains unknown.
If the channel is disabled, history remains readable but new isolated approvals
are unavailable. The original small-message synchronous retry remains separate.

For a current held message, an isolated approval control binds the exact displayed
account, receipt and parser version. Approval lasts one hour and can survive the
submitting login token's expiry. It cannot change the mailbox or run a model.
Binary PDF/Office/image/archive attachment extraction is still unsupported; a
completed job can mean only the supported text and receipt work is finished.

Queued/running/retry-wait jobs can be cancelled explicitly. A cancellation that
arrives after completion displays completion, not a false cancellation promise.
Terminal errors and outcomes use fixed explanations, without raw mail, lease
tokens or subprocess diagnostics. Refresh status manually; the page does not
poll indefinitely or automatically approve/retry mutations.

If a submission's response is uncertain, the same control retains its idempotency
UUID for an explicit retry in the unchanged view. Refresh saved history to reconcile
what happened. Do not repeatedly approve with new keys after a network error.
Changing account, credential, page or review generation invalidates old controls.
The browser does not save credentials, job state or approval keys to local storage.

## History contract

`GET /v1/accounts/{account}/processing/jobs` requires current owner membership and
evidence-read scope. Optional `limit` is 1–50; optional `after` is a job UUID from
the same tenant/account. The server returns only the public job projection,
`results`, `next_after`, `limit` and `mailbox_effects: false`.

Newest approvals appear first using immutable creation time and UUID as the
tie-breaker. All states are included. This is a live list, not a frozen export;
refresh the first page to see new approvals or updated outcomes. Unknown/foreign
anchors are 404; invalid values are 422; insufficient scope is 403. Read audit
records `recovery.jobs_read` without message content. Migration 0011 adds a history
index; it does not change approval lifetimes, worker grants or job transitions.

## Tests and preview

Python tests cover API dispatch, pagination, same-time ordering, limits, actor/tenant/
account boundaries, durable history after service recreation and read-only state.
Independent Node contracts cover explicit approval, idempotency, cancellation
races, malformed responses, paging and stale asynchronous callbacks. The original
session/security suite remains required. Run both:

```sh
node --test tests/web_session.test.cjs tests/web_processing.test.cjs
```

For a **synthetic visual preview only**, run:

```sh
.venv/bin/python tests/browser_preview.py --synthetic-preview
```

Open its printed loopback URL. The fixed non-secret demo token is
`synthetic-preview-only`; the account is `00000000-0000-4000-8000-000000000001`.
This fixture serves actual UI assets but simulates API jobs in memory, uses no
database or Docker and cannot validate durable execution. Stop it after the review.
Actual PostgreSQL and restricted-container acceptance remain separate CI tests.
The build receipt distinguishes browser observations from DOM and backend tests.

## Rollout and rollback

Apply additive migration 0011 with operators aware of index-build locking. Deploy
compatible API/assets together; keep bootstrap ingress loopback-only. On rollback,
retain the index, jobs and evidence. Hiding controls does not cancel approved work;
use the existing cancellation endpoint or stop the controller if needed.
Production login, supervised processing, browser accessibility/performance at
scale, real provider acceptance and binary extraction remain release gates.
