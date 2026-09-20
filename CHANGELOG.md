# Changelog

## Unreleased — 2026-09-20

- Added resumable Fastmail read-worker library, database-clock leases, stale-worker
  fencing, account-binding checks, query-state pagination and baseline-preserving restart.
- Added bounded retry deadlines, content-free operational outcomes and explicit
  auth/protocol/parser/cursor-expiry pauses; no live scheduler or enrollment.
- Added current mailbox/keyword metadata without replacing raw-body evidence.
- Hardened provider URL, response, metadata and checkpoint validation.
- Added synthetic HTTP-to-PostgreSQL, competing worker, crash/replay, malformed
  provider and failure tests; retained real-mailbox and full reconciliation gates.
- Corrected database infinity timestamps after CI caught status-decoding failures.
- Refined build order, migration/rollback guidance and honest release boundaries.

## 0.1.0 — 2026-09-19

- Published private GitHub architecture/product pack and bounded implementation.
- Added Postgres evidence/version/search/control schemas, forced RLS and composite ownership keys.
- Added atomic page ingestion with idempotency, stale-cursor checks and immutable event/evidence history.
- Added owner-only scoped API authentication, evidence/search, typed proposals and human review.
- Added browser review UI with text-only mail display and memory-only token handling.
- Added attachment receipts/events, duplicate links, bounded text extraction and explicit deferred outcomes.
- Added read-only JMAP protocol slice, inference validation/routing and rank-fusion helpers.
- Added real PostgreSQL CI tests, dependency lock, developer container and local run instructions.
- Reviewed Factory intake patterns; staged five Factory improvement proposals without changing Factory.
- Refreshed OSS activity/license caveats and compared AWS/Supabase/Neon hosting.

Not shipped: live mailbox synchronization, sending/deletion, approved-rule application,
production auth/deployment, binary extraction sandbox, MCP transport or live model adapters.
