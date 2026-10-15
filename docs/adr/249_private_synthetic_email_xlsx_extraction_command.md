# ADR-249 — Private exact-approved synthetic Email XLSX extraction command

Status: implemented on an open PR with fictional command-to-PostgreSQL tests; actual immutable-image and hosted execution remain open.

## Decision

Expose ADR-240's private `EmailXlsxResults.record` through `masterbrain email extract-approved-xlsx`. The operator names exactly one existing `xapp_` approval, a closed version-1 private config, and `--tenant-bound-db`. The config pins one Email account, an immutable `sha256:` document image, an absolute Docker binary, and private credential/token paths. Optional encrypted-object root and keys paths are paired and validated. The token must be a worker credential with **exactly** `email.document.process` and `email.evidence.read`; the PostgreSQL login must be DBA-bound to the same tenant. The command never accepts workbook bytes, a mailbox query, a processor version from the browser, or a live-provider account.

Check mode authenticates the worker, checks the tenant-bound database login, synthetic active account, private blob configuration and pinned image syntax. It does not read the selected approval, retained MIME or workbook, start the processor, or write a result. Execute mode checks that the approval belongs to the configured account **before** loading MIME, then ADR-240 rechecks approval expiry, owner membership, source currentness, worker credential and exact processor image before and after isolated extraction. Only a complete bounded text result is sealed in the immutable private result table. A replay returns the existing digest/count receipt after renewed authorization, without publishing or modifying mail.

The human owner may then use ADR-246's first-party result-review screen; a different, separately scoped publication worker consumes the human review. This extraction result is not searchable yet, not a cell-level citation and not a financial fact. No live Fastmail enrollment or FOS-Master change follows.

## Evidence and remaining gates

Eleven controller unit cases cover check mode without selected data, exact worker scopes, malformed/unbound configuration, synthetic-only account refusal, CLI parsing and execution reauthentication. A disposable PostgreSQL test uses a distinct worker actor and tenant-bound login, checks that check mode writes no result, rejects a different valid synthetic account before processor invocation, seals one approved result through the restricted-processor simulation, replays it and rejects an admin/unbound login. A separate service test checks account mismatch before raw read. The complete fictional local Python/PostgreSQL suite passed at this code state (3,837 passed, 19 skipped; 693/694 PostgreSQL-marked executed). The actual pinned image, populated restore on this head, hosted CI, browser accessibility and independent review remain open gates.
