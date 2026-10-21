# ADR-243 — Restricted command for one reviewed Email XLSX publication

Status: implemented on an open PR with fictional command-to-PostgreSQL coverage. Actual-image execution, hosted exact-head CI and independent populated restore remain open. No live Email account is authorized.

## Decision

Expose ADR-242's private worker publication through `masterbrain email publish-reviewed-xlsx`. The operator must name one existing `xrev_…` review and a UUID idempotency key. A closed version-1 private configuration pins one Email account and paths to a private credentials file and token. The credential must be a **worker** token with exactly `brain.source.ingest`, `brain.document.publish` and `email.evidence.read`; no human or assistant token can run the command. The DSN is supplied separately through `MASTERBRAIN_DSN`, and `--tenant-bound-db` is mandatory.

`--check` validates configuration, credential and tenant-bound database login without reading the selected review/result, publishing a document or constructing a parser. Execution binds the selected review to the configured account, reauthenticates the worker inside the publication transaction and again before returning, then invokes ADR-242's currentness/result/owner and SQL receipt guards. Reusing the same idempotency key returns the existing content-free receipt. Command errors suppress sensitive details. It never contacts Fastmail or modifies a mailbox.

This closes an operability gap: a real worker credential can now reach the reviewed bridge without a hand-constructed Python context. It does not make the review screen, live source, cell citations or FileOS cutover accepted.

## Acceptance

Unit tests cover exact scopes, wrong client kind, malformed configuration and review ID, account binding, check-mode nonpublication, and reauthentication. A fictional PostgreSQL test uses a distinct worker actor and tenant-bound login to check, reject a wrong account, publish, replay and find the cited text through Email-family search. The full synthetic suite, actual-image case, hosted CI and independent restore are separate merge gates.
