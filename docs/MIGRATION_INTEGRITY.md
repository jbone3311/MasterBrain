# Migration integrity contract

This contract closes [issue #5](https://github.com/jbone3311/CW-EmailBrain/issues/5)
without changing the checksums of migrations already applied. The design is
[ADR-091](adr/091_migration_integrity.md); hosted verification is pending.

## Identities and visibility

Schema migrations run through the explicit administrator command with a dedicated
migration credential. Its effective PostgreSQL role must be `rolsuper` or
`rolbypassrls`, must have the required DDL ownership/permissions, and must not be
used by the API, workers or source adapters. The migrator checks that property before
any schema or migration-ledger mutation. Runtime and worker roles remain
`NOSUPERUSER NOBYPASSRLS`, non-owning and constrained by forced tenant RLS.

Forced RLS applies even to a table owner. With no `email_brain.tenant_id` setting,
the policy on `messages` and `message_versions` hides all rows from an ordinary
role. `SET LOCAL row_security = off` is a useful fail-closed visibility test, not
an authorization grant: an ordinary role attempting an affected read gets an error.

## Forward correction

The next additive migration must perform these operations in one transaction:

1. Recheck migration-role visibility and reject any current-message/version parser
   mismatch using the exact join and predicate from 0008.
2. Insert a `message_sync_state` row for each current `messages` key that has no
   corresponding ledger key, with `deleted`, `quarantined`, or `ready` derived
   from current message state in that precedence order.
3. Leave every existing ledger row untouched, including newer quarantined/deleted
   states and event keys.
4. Assert that no current-message key remains missing and record the migration only
   when every check succeeds.

The guard deliberately stops before repair if mismatches exist. An operator must
inspect immutable evidence and approve a separate corrective procedure; a parser
version must not be rewritten merely to make the guard pass. Retrying the forward
migration after the reviewed repair is safe. Existing 0006 and 0008 files remain
byte-identical because the migrator enforces their checksums.

## Acceptance evidence

- A populated pre-0006 disposable database reproduces the missing row under a
  non-bypass owner; a pre-0008 mismatch reproduces the false-negative guard.
- The corrected migrator rejects that role before applying any pending migration,
  while a dedicated privileged migrator executes DDL and reads across tenants.
- A mixed-tenant fixture covers ready, deleted and quarantined legacy messages, newer existing
  ledger rows, parser mismatch rollback, repeated runs and empty databases.
- After repair, a privileged audit finds zero missing current-message keys and zero
  parser mismatches; tenant-scoped runtime reads retain RLS isolation.
- Sync status and reconciliation tests prove repaired legacy rows are counted and
  provider absence can be discovered. CI and a populated logical restore pass.

## Operator sequence

Use an approved disposable/staging environment first. Record the exact migration
role attributes and a read-only count of missing keys and parser mismatches under
that role. Stop on mismatches and preserve the backup/evidence for review. Stop old
workers, apply the additive migration with the migration credential, confirm zero
remaining missing keys and unchanged pre-existing ledger rows, then run the normal
restore and release gates. Keep privileged credentials outside application/runtime
configuration and logs. Do not treat a successful migration receipt from an older
non-bypass deployment as proof that its backfill ran.
