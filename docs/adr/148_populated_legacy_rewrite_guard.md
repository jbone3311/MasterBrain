# ADR-148 — Refuse implicit populated legacy heap rewrites

Status: accepted for administrator migration safety. This is a refusal gate,
not an online migration or approval to run a populated production upgrade.

## Context

Legacy migrations 0008 and 0009 add stored generated columns to
`message_versions` and `raw_objects`. PostgreSQL rewrites each populated heap
under `ACCESS EXCLUSIVE`; the latter can contain large MIME values. The
ordinary migrator currently executes these files without distinguishing an
empty installation from a populated one. Issue #9 also tracks later DDL and
the transaction-only migration architecture; this decision addresses only
the two known generated-column rewrites.

## Decision

- Before unapplied 0008 or 0009, the administrator migrator takes a nonwaiting
  `SHARE` table lock and checks whether the exact target table has any rows.
  That lock allows readers but fences inserts between the check and the
  subsequent DDL. A busy writer makes the migration fail immediately; a
  concurrent reader that blocks the stronger DDL lock reaches a five-second
  transaction-local lock timeout instead of waiting indefinitely.
- The default refuses a populated target with a content-free diagnostic naming
  the migration and table. The failed migration receives no ledger row, and
  its transaction releases the lock without changing that migration's schema.
- `email-brain migrate --allow-populated-rewrite` is an explicit operator
  override for a reviewed maintenance window, backup/restore plan, measured
  disk headroom and lock budget. It retains the original SQL and all existing
  integrity checks; it does not make the upgrade online or independently safe.
  The library argument is keyword-only and strictly boolean.
- Existing checksums and historical SQL files are not edited. Already-applied
  migrations are checked by checksum as before and do not require the flag.

## Acceptance and rollback

PostgreSQL tests must show default refusal for both populated tables, immediate
refusal under a concurrent writer, bounded refusal under a concurrent reader,
no failed-migration ledger row, and the
existing explicit populated upgrade/provenance checks under the override.
Empty-schema installation and rerun remain unchanged. Rollback is to retain
the refusal and use an operator-reviewed staged/online alternative; do not
drop evidence or disable checks to force a migration. Issue #9 remains open
until populated-scale lock/disk evidence and an acceptable upgrade path cover
all identified DDL, including later indexes.
