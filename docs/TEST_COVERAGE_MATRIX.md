# Test coverage and limits

Updated 2026-09-21. These are executable behavior checks, not a claim of 100% line
coverage or production readiness. All message content is synthetic. Exact results
and tested commits belong in [BUILD_RECEIPT.md](BUILD_RECEIPT.md).

| Area | Executable tests | Still needed before production |
|---|---|---|
| Browser session backend | Fake code endpoint with genuine RSA access verification, PKCE/state/replay, cookie/Origin/CSRF and fetch metadata, races/cancellation/logout, finite capacity/expiry, private config redaction and real SQL isolation/revocation tests | Operator/TLS and owner UI integration, actual browser/accessibility acceptance, authorized issuer/MFA, distributed availability and rate limits |
| Response streaming | Sixteen fake-stream cases across Fastmail/Gmail/Graph/Ollama: slow bytes, delayed empty EOF, fragmented success, overflow and closure; five regression failures proved against the old implementation | Real network fault/soak tests and hosted supervision; cooperative checks are not hard process deadlines |
| API identity | Generated RSA keys/fake RFC and Entra issuer, closed profiles, algorithm/audience/claim denials, bounded key cache/rotation/outages, real SQL/API mapping/RLS/revocation/admin audit and populated identity restore | Browser/session, real issuer registration/MFA policy, enrollment/admin UX, service identities, rate limits and independent security acceptance |
| Approved PDF documents | Separate human/worker scopes, schema/SQL ownership, cancellation/revocation/source/expiry/lease races, immutable revisions, page citations, opt-in FTS, restricted-worker SQL/search and restore; explicit CLI/config/preflight/restart, credential and owner UI/SQL-to-DOM tests | Browser/accessibility acceptance, scanner/live policy, hosted supervision, broader quality and soak |
| Read operator | Private-file/closed-config/exact-scope checks, explicit execution flag, no-request/no-claim preflight; fake HTTPS plus real SQL restart, source/owner/token/lease changes, pause/retry and encrypted large-source readback | Production service identity, enrollment/resume administration, hosted supervision/alerts, live acceptance and soak |
| Durable recovery jobs | API approval/cancel/status/history, account-bound cursor pagination, worker authority, SQL RLS/immutable approvals, concurrent claims/idempotency, lease/expiry/source/revocation fences, bounded retries, actual-container pipeline and restored job states | Hosted service identities, supervision/alerts and extended multi-controller soak |
| Isolated large MIME | Strict output schema/hash/Unicode/allocation budgets, container pre-disclosure controls, timeout/output flooding, exact-owned cleanup, processor-version fences, explicit real-container to PostgreSQL/search CI suite | Hosted controller, sandbox escape/load review, scanner and binary extractors |
| Encrypted raw objects | AES-GCM/AAD, key rotation, tampering, ownership/symlinks, crash/fsync, duplicates, staged orphan inventory, SQL constraints, large-message holding/restart and missing-object restore refusal | Hosted Blob/KMS, key-backup recovery, retention/purge and offsite durability |
| MIME | Plain/HTML alternatives, Unicode, unknown charset, truncation, NUL fields, size bounds, 1,000 seeded random byte inputs | Extended fuzz campaign, independent parser security review |
| Attachments | Path names, duplicate receipts, CSV/plain extraction, binary/active-content deferral, depth/count limits; separate approved PDF path above | Office/OCR extraction, malware fixtures and sandbox escape tests |
| Realistic attachment formats | Nine deterministic in-memory MIME cases; 31 payload/hash/ZIP/XML/PNG/encoding checks; 36 byte-preservation checks across four mocked provider formats | Approved external corpus comparisons and live provider conformance; Office application acceptance |
| Calendar evidence | 73 parser and 11 independent security tests; named/unnamed calendar MIME, UTF-8 byte folding, syntax/budget failures, inert alarms, METHOD consistency, real DB FTS/history/replay | Full calendar semantics, recurrence/timezone computation, historical reprocessing and calendar actions |
| Imports | 256-message HTTP-to-Postgres corpus, process recreation each page, varied attachments, initial and incremental sync | Live disposable-provider conformance and realistic mailbox sizes |
| Gmail | Fixed-host GET transport, account binding, History paging/expiry, raw and minimal response shapes, quota/auth distinction, untrusted notifications | OAuth enrollment, durable worker, authenticated Pub/Sub and live conformance |
| Graph | Fixed-account/folder opaque cursors, immutable IDs, folder removal is not global deletion, webhook-hint validation, MIME bounds | Durable per-folder workers, subscription lifecycle, live conformance |
| IMAP | Injected UID session, read-only selection, UIDVALIDITY races, complete high-water inventory, PEEK size bounds and reset | Pinned network library, verified TLS/account binding, hard wire bounds, durable worker |
| Recovery | History expiry, certified inventory, empty mailbox, query churn, multiple reconciliation pages, partial inventory refusal, v1 upgrade | Multi-day soak and provider-specific race/retention windows |
| Poison mail | Exact rejected bytes retained; immutable receipts; good mail progresses; human retry; concurrent retry/provider update races; hash verification; parser drift rollback; old citations stable; opt-in large-object quarantine | Bulk historical reprocessing, alerting, larger isolated parsing |
| Consistency | Atomic evidence/checkpoint, duplicate event checks, collision rollback, lease fencing, eight concurrent claims, crash-after-commit | Production concurrency/load and database failover |
| Retrieval | Body/attachment FTS, opt-in latest-current document text, stable historical evidence, tombstone/quarantine exclusions | Recall benchmark, vector retrieval, entity/state filters |
| Bootstrap authorization | Expired/invalid local tokens, server-bound context, denied scopes, owner membership revocation, forced RLS, cross-tenant keys and context reset | Full browser/MFA lifecycle, invitation/member/account grants, rate limits; implemented configured-token boundary is covered in API identity above |
| API | Authentication, bounded bodies, validation without input echo, secure response headers, status counts, proposals/reviews, absent write endpoints | Browser accessibility, CSRF/session/OAuth threat tests for future login |
| Owner UI | Three Node DOM-contract suites for session/rules, MIME processing and PDF review/search; same-key retries, cancellation races, malformed responses, stale views and cursor preservation; four real SQL/API-to-DOM PDF cases | Full browser automation, accessibility, scale/pagination stress and production login; exact counts belong in the build receipt |
| Control | Persisted rule simulation/activation/rollback, stale receipts, competing writes, actor/tenant isolation, REST lifecycle, virtual-only effects; pure protected-class veto | Rich persisted predicates/protection policies, entities, drift evaluation |
| Models | 90 fake-server tests for opt-in local adapter, digest/metadata checks, time/size/schema bounds, grounded excerpts, rejected tools; independent disclosure tests | Actual isolated daemon/model quality, calibrated accuracy, cache and remote budgets |
| Synthetic demo | Deterministic corpus and coherent known-answer feed (EB-023), real generated formats, bounded paced/restarted replay and mismatched cursor refusal | Broader held-out scenarios, sustained soak and interactive owner acceptance |
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
