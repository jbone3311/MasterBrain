# ADR-099 — Keep archive child ledgers sealed and derivative parents exact

Status: accepted for isolated implementation; hosted verification pending.

## Context

The archive inventory ledger in migration 0023 checks member count, skip count and
observed bytes when an inventory is inserted. Its child tables remain append-only
but permit later inserts. A new child can therefore make a previously balanced
inventory false without changing its immutable parent or receipt. The existing
FileOS run ledger avoids this with deferred triggers on both parent and children.

`brain_provenance.output_id` has no database reference to the normalized document
it names. Three archive derivative receipts require a `parent_source_version_id`
but do not bind it to their inventory's source version. Their current-search
queries recheck the relationship, but retained history can still contain a
misbound receipt. These gaps were proposed in Factory review PR #11 and confirmed
against current migrations and writers. PR #11's migration number 0029 collides
with the already integrated Email repair and cannot be adopted wholesale.

## Decision

- Add forward-only migration 0033. Before creating constraints, lock the archive
  inventory/member/skip tables against concurrent writes and refuse any existing
  count/byte mismatch. Do not silently repair a historical ledger.
- Install deferred `AFTER INSERT` constraint triggers on both archive child tables.
  They resolve the parent inventory and compare the final member/skip counts and
  observed-byte sum. A missing or tenant-invisible parent fails closed. The
  existing inventory-insert trigger remains in place.
- Add a validated tenant-composite foreign key from provenance output to its
  normalized document. Do not constrain provenance `input_id` to evidence:
  archive provenance also names inventory IDs, so that input is polymorphic.
- Add a unique `(tenant_id,id,source_version_id)` identity on archive inventories
  and validated composite foreign keys from each text, document and image receipt's
  `(tenant_id,inventory_id,parent_source_version_id)` to that identity. This
  enforces exact parent equality, stronger than an existence-only version FK.
  Existing mismatches stop the migration for reviewed repair.
- No applied migration is edited; no existing evidence is rewritten, deleted or
  reclassified. PR #11's duplicate truncation change is excluded because
  ADR-092/migration 0030 already covers it. Workflow suggestions are separate.

## Verification

Use disposable PostgreSQL and fictional archive evidence. Prove both late member
and late skip insert fail at commit without changing the sealed ledger. Prove
malformed provenance output and a receipt naming a different valid parent source
version fail at the database boundary; inspect all three receipt FK definitions.
Prove a populated pre-0033 upgrade preserves valid retained rows and refuses an
already-corrupt child ledger. Run full CI, populated restore and documentation
inventory on the exact PR head. An individual test passing without a database is
not evidence for these constraints.

## Rollback and limits

Pause archive publication before a migration failure, retain the database and
backup, inspect the offending immutable rows and repair only through a separate
reviewed evidence procedure. Do not disable guards or down-migrate automatically.
These constraints protect database integrity; they do not attest to the correctness
of untrusted archive bytes or authorize FOS-Master cutover. FOS-Master remains
unchanged.
