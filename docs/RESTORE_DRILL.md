# Synthetic PostgreSQL backup/restore drill

## Scope

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
- Body and extracted-attachment full-text search.
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
text attachment is extracted, one fake PDF remains deferred and malformed empty
MIME produces retained quarantine evidence. No real provider or model is contacted.

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

This proves neither cloud encryption/KMS nor managed snapshots/PITR, object-store
consistency, disaster-region recovery, key-loss handling, real-mail scale or
production RPO/RTO. The reported elapsed time is a tiny synthetic drill, not a
service recovery guarantee. No production backup command or retention system is
introduced. Future operational drills need explicit authorization and independently
verified backup/key/identity access. See [ADR-023](adr/023_synthetic_restore_drill.md).
