# ADR-091 — Verify migration visibility and repair the legacy Email ledger

Status: implemented on migration-integrity branch; hosted verification pending.

## Context

[Issue #5](https://github.com/jbone3311/CW-EmailBrain/issues/5) identified two
data-dependent migrations that assume unrestricted visibility. Migration 0006
backfills `message_sync_state` from `messages`; migration 0008 checks current
`messages` against `message_versions` for parser-provenance mismatches. Both source
tables have forced tenant RLS. The migration runner sets no tenant context. A
non-superuser, non-`BYPASSRLS` table owner therefore sees zero rows for these reads,
and both migrations can commit without doing their intended work. Existing CI applies
migrations as PostgreSQL `postgres`, so it does not test this failure mode.

Missing sync-state rows do not erase messages or raw evidence. They undercount sync
status and can cause reconciliation to omit a legacy message that disappeared from
the provider. A missed provenance mismatch violates the explicit stop-and-repair
promise for migration 0008.

## Decision

The migration runner must check the **effective database role** before it creates
`schema_migrations`, takes a migration lock, or executes SQL. It must require an
administrator migration identity with `rolsuper` or `rolbypassrls` and separately
retain the DDL permissions required by the schema. Reject a role without that
visibility with a clear error and no applied migration. This is a migration-only
identity; runtime and worker identities remain non-owner, non-superuser and
`NOBYPASSRLS` under forced RLS. No runtime grants or role memberships change.

Add one forward-only migration after the current schema sequence. It first checks
the exact 0008 current-message/raw-version parser mismatch predicate across all
tenants and raises an error if any row matches. Operators investigate and perform a
separately reviewed evidence repair before retrying. If the guard passes, insert
only missing `(tenant_id, account_id, provider_id)` keys into
`message_sync_state`, deriving `deleted`, `quarantined`, or `ready` from the
current `messages` row in that precedence order. Existing ledger rows may
reflect later provider activity and must
never be overwritten. The insert and migration receipt commit together. Verify
postconditions for missing keys and row counts under the privileged role before
declaring the repair complete.

Do not edit 0006 or 0008: deployed checksums are immutable. `row_security = off`
may be used in a test or diagnostic to make insufficient visibility raise an error;
it does not elevate an ordinary role or enable the backfill. No tenant-by-tenant
guess, per-tenant GUC injection, trigger disabling, RLS disablement, historical
evidence rewrite or automatic correction of provenance mismatches is authorized.

## Verification and rollout

Use a disposable PostgreSQL database populated at the pre-0006 schema. Apply the
early schema as a non-superuser, non-`BYPASSRLS` owner; insert a synthetic current
message and version with a valid tenant context; clear that context. Confirm that
the uncorrected 0006 path omits its ledger row, and that an intentional parser
mismatch is invisible to the uncorrected 0008 guard. The corrected runner must
refuse this role before mutation. A separate privileged migration identity must
backfill exactly the missing row, preserve an existing newer state, reject the
parser mismatch, and replay without duplicates or row changes. Exercise multiple
tenants, deleted and quarantined messages, empty databases and transaction rollback on guard failure.

Before rollout, use an operator-controlled read-only audit to count missing ledger
keys and parser mismatches under the actual migration identity. Stop if any mismatch
exists; preserve the database and evidence for reviewed repair. Stop old workers,
apply the forward migration with the privileged migration identity, reapply normal
runtime grants only if needed by the release, and compare counts and sync behavior.
Backup and restore remain required release gates. Rollback is forward-compatible:
stop the new runtime if necessary and preserve the additive ledger repair and all
existing evidence; do not down-migrate or delete rows.

## Alternatives rejected

- Relying on table ownership: `FORCE ROW LEVEL SECURITY` still applies to owners.
- Using `row_security = off` as an elevation: it fails closed for a role subject to
  RLS and cannot read the source rows.
- Rewriting applied migrations: checksum protection must remain meaningful.
- Rebuilding every sync-state row: later statuses may be newer than `messages`.
- Silently selecting one parser version: provenance conflicts require review.

## Scope

This decision repairs migration integrity for the existing Email capability. It
does not authorize a production mailbox backfill, FileOS cutover, source effect,
runtime RLS bypass or evidence mutation.
