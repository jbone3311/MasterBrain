# ADR-245 — Local native synthetic restore drill

Status: implemented and executed locally on PostgreSQL 17.11 with populated fictional XLSX review and publication rows. Hosted Docker restore remains open.

## Decision

Keep the existing Docker restore drill and hosted gate unchanged. Add a separate opt-in `scripts/native_restore_drill.py --run-disposable` for machines with native PostgreSQL 17 utilities but no Docker. It accepts no DSN, existing database, input archive or output path. It rejects ambient PostgreSQL configuration, creates two fresh PostgreSQL clusters under a new owner-only temporary directory, binds both to loopback-only ephemeral ports, and uses the same fictional source seed, encrypted external evidence, logical dump, restore and verification routines as the Docker drill. The target starts empty. Cleanup stops only those exact clusters and removes the temporary directory only after confirming neither is running; on uncertain shutdown it preserves the directory instead of deleting a live cluster.

The local result on 2026-10-15 verified 120 restored public tables, 424 fictional rows, five encrypted external objects, two tenants, matching content hashes and tenant/RLS isolation. The seed includes an exact-approved fictional XLSX, a deterministic extraction result, a human review, a published DataCore document and immutable bridge receipt; restored Email-family search finds that document. This is real native `pg_dump`/`pg_restore` execution, not merely a migration or mocked restore test. The fixture inserts its extraction result directly under the SQL guard; it does not prove isolated-worker execution. It also does not execute the immutable document image, reproduce the hosted container environment, authorize live data or make FOS-Master replaceable.

## Acceptance and next gate

Safety tests require an explicit opt-in, reject ambient PG settings and refuse an existing-DSN argument. Run the native drill against a fresh local PostgreSQL 17 installation and verify no temporary cluster remains. Next run the hosted Docker path with the same populated seed on the exact head, then independently review before merge.
