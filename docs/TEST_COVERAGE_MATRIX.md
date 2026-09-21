# Test coverage and limits

Updated 2026-09-20. These are executable behavior checks, not a claim of 100% line
coverage or production readiness. All message content is synthetic. Exact results
and tested commits belong in [BUILD_RECEIPT.md](BUILD_RECEIPT.md).

| Area | Executable tests | Still needed before production |
|---|---|---|
| Isolated large MIME | Strict output schema/hash/Unicode/allocation budgets, container pre-disclosure controls, timeout/output flooding, exact-owned cleanup, processor-version fences, explicit real-container to PostgreSQL/search CI suite | Hosted authenticated jobs, sandbox escape/load review, scanner and binary extractors |
| Encrypted raw objects | AES-GCM/AAD, key rotation, tampering, ownership/symlinks, crash/fsync, duplicates, staged orphan inventory, SQL constraints, large-message holding/restart and missing-object restore refusal | Hosted Blob/KMS, key-backup recovery, retention/purge, isolated job control and offsite durability |
| MIME | Plain/HTML alternatives, Unicode, unknown charset, truncation, NUL fields, size bounds, 1,000 seeded random byte inputs | Extended fuzz campaign, independent parser security review |
| Attachments | Path names, duplicate receipts, CSV/plain extraction, binary/active-content deferral, depth/count limits | Actual isolated PDF/Office/OCR extraction, malware fixtures and sandbox escape tests |
| Realistic attachment formats | Nine deterministic in-memory MIME cases; 31 payload/hash/ZIP/XML/PNG/encoding checks; 36 byte-preservation checks across four mocked provider formats | Approved external corpus comparisons and live provider conformance; Office application acceptance |
| Calendar evidence | 73 parser and 11 independent security tests; named/unnamed calendar MIME, UTF-8 byte folding, syntax/budget failures, inert alarms, METHOD consistency, real DB FTS/history/replay | Full calendar semantics, recurrence/timezone computation, historical reprocessing and calendar actions |
| Imports | 256-message HTTP-to-Postgres corpus, process recreation each page, varied attachments, initial and incremental sync | Live disposable-provider conformance and realistic mailbox sizes |
| Gmail | Fixed-host GET transport, account binding, History paging/expiry, raw and minimal response shapes, quota/auth distinction, untrusted notifications | OAuth enrollment, durable worker, authenticated Pub/Sub and live conformance |
| Graph | Fixed-account/folder opaque cursors, immutable IDs, folder removal is not global deletion, webhook-hint validation, MIME bounds | Durable per-folder workers, subscription lifecycle, live conformance |
| IMAP | Injected UID session, read-only selection, UIDVALIDITY races, complete high-water inventory, PEEK size bounds and reset | Pinned network library, verified TLS/account binding, hard wire bounds, durable worker |
| Recovery | History expiry, certified inventory, empty mailbox, query churn, multiple reconciliation pages, partial inventory refusal, v1 upgrade | Multi-day soak and provider-specific race/retention windows |
| Poison mail | Exact rejected bytes retained; immutable receipts; good mail progresses; human retry; concurrent retry/provider update races; hash verification; parser drift rollback; old citations stable; opt-in large-object quarantine | Bulk historical reprocessing, alerting, larger isolated parsing |
| Consistency | Atomic evidence/checkpoint, duplicate event checks, collision rollback, lease fencing, eight concurrent claims, crash-after-commit | Production concurrency/load and database failover |
| Retrieval | Body and attachment FTS, stable historical evidence, tombstone/quarantine exclusions | Recall benchmark, vector retrieval, entity/state filters |
| Identity | Expired/invalid tokens, server-bound context, denied scopes, owner membership revocation, forced RLS, cross-tenant keys and context reset | OIDC/MFA, invitation/member/account grants, rate limits |
| API | Authentication, bounded bodies, validation without input echo, secure response headers, status counts, proposals/reviews, absent write endpoints | Browser accessibility, CSRF/session/OAuth threat tests for future login |
| Owner UI | 25 Node DOM-contract tests: explicit recovery click/parser binding, session/account/refresh races, generic errors, simulation/activation, rollback, text-only rendering; prior synthetic search/evidence smoke | Full browser automation, accessibility, pagination stress and production login |
| Control | Persisted rule simulation/activation/rollback, stale receipts, competing writes, actor/tenant isolation, REST lifecycle, virtual-only effects; pure protected-class veto | Rich persisted predicates/protection policies, entities, drift evaluation |
| Models | 90 fake-server tests for opt-in local adapter, digest/metadata checks, time/size/schema bounds, grounded excerpts, rejected tools; independent disclosure tests | Actual isolated daemon/model quality, calibrated accuracy, cache and remote budgets |
| Synthetic demo | Deterministic corpus, bounded count, mid-import crash/resume, complete replay, mismatched cursor refusal | Interactive owner acceptance |
| Release | Locked dependencies, lint, strict types, migration replay, document links, container build/CLI; actual disposable PG17 logical restore with hash/RLS/search checks | SBOM/advisory/signature gates, managed-cloud restore/PITR and disaster recovery |

## Interpreting the results

The larger mailbox test imports 256 emails, applies seven changed IDs (new,
updated, deleted and poisoned), then simulates expired history with twenty unseen
deletions. It checks resulting counts and searches after certified reconciliation.
It is bounded fault/pressure testing, not a throughput benchmark or long-running soak.

`caught_up` describes provider cursor progress, not complete extraction. Check
current quarantine counts and attachment accounting. No test sends or deletes
provider mail, accesses a real mailbox, calls a model, or provisions paid hosting.
Gmail/Graph/IMAP now have offline read-contract tests, but not durable integration
workers or live-account acceptance. MCP and production restore remain planned—not
covered by pretend green tests for unimplemented features.
