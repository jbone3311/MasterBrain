# ADR-250 — Fictional Email XLSX alpha round trip

Status: implemented as a disposable PostgreSQL integration test on an open PR. It is a synthetic workflow proof, **not** live Fastmail, an actual-browser session or an actual immutable-image execution.

## Decision

Treat the ADR-239–249 steps as one contract and test them together. A fictional Email with one XLSX is ingested and bridged. A human owner searches, opens its Email evidence and identifies the exact attachment receipt, then calls the human-only source-attached approval API. Before the separate extraction worker runs, result inspection refuses and no processor is called. A distinct worker actor with only `email.document.process` and `email.evidence.read` uses a tenant-bound PostgreSQL login to check, then execute `extract-approved-xlsx`; the restricted processor is simulated with the same request/response contract as the isolated child. The owner inspects the saved, complete digest-bound result, and its real API response is passed through the first-party JavaScript review contract. A separate explicit human review creates an `xrev_` ID. A **different** worker actor/login with only `brain.source.ingest`, `brain.document.publish` and `email.evidence.read` checks then executes `publish-reviewed-xlsx`. Current Email-family search and a separately scoped evidence-content request find the published, occurrence-cited text. Pausing the Email source hides both search and direct content.

The test asserts false mailbox/publication effects before the correct stage, no result from check mode, no document visibility before publication, stable source attachment/parent identity, exact UTF-8 text hash, one approval/result/bridge receipt, and no direct access after source pause. It uses no provider account, personal workbook, real token, live source folder or FOS-Master mutation.

## Limits and next gates

This is one bounded fictional happy path plus source-pause denial, not a stress corpus or a claim that the actual Docker image, browser accessibility, hosted CI, provider reads, cell-level citations, financial facts or FileOS replacement work. Lower-level suites separately cover malformed workbooks, expiration, replay, wrong-account and revoked-owner paths. Before an owner pilot, run the complete workflow with the pinned actual image and real browser, obtain hosted exact-head/restore/strict-runtime gates and independent review, then explicitly authorize a narrow live-source window. FOS-Master remains the unchanged donor/runtime authority.
