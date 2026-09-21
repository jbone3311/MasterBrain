# Synthetic PostgreSQL backup/restore drill

Latest runtime recheck: **f73c235**,
[run 35589125878](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35589125878),
passed 2026-09-21 after the owner PDF screen and attachment-contract correction.
The unchanged fixture verified **26 tables, 142 rows, two tenants and four encrypted
objects**, matching hashes, RLS and database-only refusal. **14.37 seconds** includes
disposable startup, not production RTO/PITR or hosted key recovery. The 29 restore
safety tests also passed. This is not browser or real-PDF extraction proof; those
have separate acceptance paths in the [build receipt](BUILD_RECEIPT.md).

Historical runtime recheck: **73a8459**,
[run 35584256115](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35584256115),
passed 2026-09-21 after the separate PDF operator command/shared-controller changes.
**26 tables, 142 rows, two tenants and four encrypted objects**, matching hashes,
RLS and database-only refusal passed. Elapsed **18.24 seconds** includes disposable
startup; this is not managed PITR, a key-loss recovery drill or production RTO.
The restore fixture is unchanged; actual CLI/PDF-container acceptance runs separately.

Historical verified restore implementation: **a2c5957**,
[run 35579931717](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35579931717),
passed 2026-09-21: **26 tables, 142 rows, two tenants and four encrypted objects**.
It adds completed/cancelled/pending document jobs, immutable page evidence and
authorized document FTS. All table/raw hashes and RLS checks passed; SQL-only and
missing-object restores were refused. Elapsed 19.71 seconds includes disposable
startup, not a production RTO. The known-answer synthetic result adapter proves
restoration, not actual extraction; restricted-container checks run separately.

Historical verified implementation: **814197a**, [run 35568746120](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35568746120),
passed 2026-09-20 Pacific. Mixed inline/external evidence: **24 tables, 119 rows,
two tenants, four encrypted objects**, equal hashes and restored authorization.
Completed, cancelled and queued processing grants retained their exact state and
expiry; bounded processing history survived restoration and cross-tenant status
was denied. The restore's empty-MIME synthetic processor
tests job durability, not isolation (actual-container checks run separately in CI).
Database-only and empty-object restores were refused. Elapsed 23.77 seconds
includes container startup; not a production RTO. See [build receipt](BUILD_RECEIPT.md).

The following test-only correction (`98bb6f2`) changes no runtime, schema or restore
code. This restore receipt applies to its unchanged implementation, not a new run.

Historical verification: code `e3695d8`,
[restore run 35560344225](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35560344225),
passed on 2026-09-20 Pacific. The expanded fixture includes searchable calendar
attachments: 22 tables, 77 rows, two tenants, equal hashes and recovered search/RLS.
Elapsed 20.52 seconds includes container startup; not a production RTO. The owned
test container and temporary archive were removed. The earlier receipt below is
historical and covers the previous smaller fixture.

Verified 2026-09-20 Pacific at code commit `d5f8f47`:
[restore run 35556627775](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35556627775)
passed with 22 tables, 73 rows and two synthetic tenants. Content hashes matched;
recovered evidence, attachments, rules, search and row-level authorization checks
passed. Elapsed drill time was 23.82 seconds including container startup—not a
production RTO or large-mailbox performance measurement. The exact owned test
container and temporary synthetic archive were removed by the drill.

## Scope

The current expanded drill seeds mixed legacy inline and encrypted external raw
objects, including two messages above the parser budget. Ciphertext is copied to
an independent temporary backup and restored to a fresh object directory. Keys are
random, tenant-bound, held separately in memory and never archived/uploaded.
Database-only restoration must fail; supplying an empty object tree must also
fail. Only after ciphertext restoration may all raw hashes and application checks
pass. This checks the local object contract, not Azure Blob/KMS or key-backup recovery.
See the current [build receipt](BUILD_RECEIPT.md) for the last verified commit.

This is an executable **logical dump and restore**, not merely a manifest check.
It creates a completely new PostgreSQL 17 Docker cluster, seeds two fake tenants,
runs `pg_dump` in custom format, restores into a fresh empty database using
`pg_restore`, and checks the result. Both utilities come from the same PostgreSQL
17 container as the server, avoiding a host-client major-version mismatch.

PostgreSQL supports custom archives with selective reconstruction via `pg_restore`;
a database dump does not include global roles. This drill deliberately restores
without original owners/ACLs and creates a fresh restricted runtime role using
reviewed application grants. [pg_dump](https://www.postgresql.org/docs/17/app-pgdump.html),
[pg_restore](https://www.postgresql.org/docs/17/app-pgrestore.html).

## What is checked

- Row counts and deterministic row-content digests for **every public table**,
  compared before any post-restore application reads add new audit events.
- Each raw MIME object's SHA-256 recomputed from its restored bytes.
- Stable evidence IDs, excerpts, metadata and attachment receipts.
- Body, extracted-attachment and opt-in document full-text search; immutable
  document page excerpts/provenance and completed/cancelled/pending grants.
- Preserved approved proposals and evidence links, quarantine state and cursors.
- Human-reviewed rule proposals, simulation receipts and active revision 1 per
  tenant; restored search classifications retain distinct tenant categories and
  foreign simulation receipts remain inaccessible. Immutable evidence is unchanged
  by rule activation or restoration.
- Forced tenant RLS, unfiltered SQL isolation, cross-tenant search/evidence denial,
  missing-context fail-closed behavior, runtime denial of raw mutation, rejection
  of privileged application runtime roles and restored immutable-evidence triggers.
- Applied migration checksums remain unchanged; no new migration runs after restore.

All input is generated synthetic mail with `example.invalid` addresses. One plain
text attachment is extracted, a generated PDF keeps its original deferred receipt
and gains a separate known-answer extraction, and empty MIME produces retained
quarantine evidence. No real provider or model is contacted.

## Safety boundaries

The script accepts **no existing DSN, input archive, target database, host or output
path**. Source/target/control names use a random `email_brain_test_restore_*` prefix
inside its own new cluster. Docker is pinned to the local Linux UNIX socket;
PostgreSQL host and hostaddr are explicitly loopback. Ambient `PG*` configuration
is rejected before any Docker action, preventing service files or host overrides.
No host volumes are mounted. The only published port binds to `127.0.0.1`.

The dump exists only in a private temporary directory (0700), as a 0600 file.
It is not printed, committed or uploaded. The archive is deleted after restore;
cleanup removes only the exact container ID whose name and random ownership label
match this invocation, including its anonymous data volume. No prune or existing
database cleanup command runs. A failed ownership check refuses removal.

The final receipt contains only pass/fail, counts, elapsed time and validation
flags. Utility/database errors are suppressed because they may include rows or
credentials. On runner termination, the disposable hosted runner is the final
cleanup boundary; do not run this against a long-lived production Docker host.

## Running and CI

Run on a disposable **Linux runner with Docker**, after installing locked dev
dependencies:

```bash
uv run python scripts/restore_drill.py --run-disposable
```

No cloud/mail/database secrets are required. The dedicated GitHub workflow
`Synthetic PostgreSQL restore drill` runs on relevant pushes/PRs and can be
dispatched manually from Actions. CLI dispatch after the workflow is published:

```bash
gh workflow run restore-drill.yml --repo jbone3311/CW-EmailBrain
gh run list --workflow restore-drill.yml --repo jbone3311/CW-EmailBrain
```

Offline guard tests run with `pytest -q tests/test_restore_drill.py`. Those tests
do **not** prove a successful PostgreSQL restore. Only a passing dedicated Docker
workflow establishes that receipt for the corresponding commit. Local development
without Docker can run the guards but must not claim the real drill passed.

## Still not solved

This proves neither cloud encryption/KMS nor managed snapshots/PITR, live concurrent
cloud object-store consistency, disaster-region recovery, key-loss handling, real-mail scale or
production RPO/RTO. The reported elapsed time is a tiny synthetic drill, not a
service recovery guarantee. No production backup command or retention system is
introduced. Future operational drills need explicit authorization and independently
verified backup/key/identity access. See [ADR-023](adr/023_synthetic_restore_drill.md).
