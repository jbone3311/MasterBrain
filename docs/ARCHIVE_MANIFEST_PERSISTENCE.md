# Archive manifest persistence plan

Status: implemented and accepted in runtime `03dbb98` with correction `08ccb68`.

## Purpose

Persist an accepted hash-only archive inventory without turning archive members into
evidence or search documents. This is the audit/provenance bridge between the accepted
isolated worker and a future, separately approved one-member read contract.

## Closed write contract

One explicit transaction receives a tenant context, idempotency key, exact existing
FileOS source version, exact immutable archive processor version and a validated
`ArchiveResult`. It accepts only `complete/bounded_archive_v1` or
`partial/bounded_archive_partial_v1` results. The source identity repeated by the
result must exactly match the database version and that version must still be the
source item's current version when the transaction commits.

Bomb, duplicate, unsupported and invalid results are diagnostic-only and cannot create
an inventory, member, skip, receipt, evidence, provenance, document, chunk or change
row. The transaction never receives or stores member bytes.

## Additive records

- `brain_archive_inventories`: stable inventory identity, parent source/item/version,
  processor version, canonical result digest, format, status/reason and bounded counts.
- `brain_archive_members`: ordered safe locator, member hash, declared/observed size,
  media hint, depth, optional parent-container locator and container flag.
- `brain_archive_skips`: ordered safe diagnostic locator, closed reason, depth and
  optional parent-container locator.
- `brain_archive_inventory_receipts`: tenant/actor/idempotency key, canonical request
  hash and inventory identity.

All four tables are forced-RLS and append-only. Deferred constraint triggers prove the
stored member/skip row counts and aggregate member bytes match the sealed inventory.
The inventory has one accepted result per source version and processor version; an
exact retry returns the original result, while key reuse or deterministic-result drift
is a conflict.

## Explicit absences

This tranche creates no child `brain_source_items`, `brain_source_versions`,
`brain_evidence`, `brain_normalized_documents`, `brain_chunks`, `brain_change_events`
or index-generation rows. It adds no API, CLI, scheduler, member reader or search
visibility. Historical manifests remain immutable but are not interpreted as current
child evidence.

## Acceptance

1. unit validation rejects terminal results, source/processor mismatch, unbounded
   values and canonical digest drift before SQL;
2. real PostgreSQL proves exact replay, key conflict, stale-current refusal, atomic
   rollback, deferred ledger checks and concurrent replay;
3. foreign tenants cannot read or reference the manifest; forced RLS still applies to
   the runtime role;
4. all four tables reject update/delete and restore with their rows and relationships;
5. searches and change feeds are byte-for-byte unchanged by persistence;
6. the isolated worker, live donor baseline and FOS-Master clean pin remain green.

All gates passed in CI 35783950712 and restore 35783950915. The accepted implementation
creates no archive-derived evidence or search visibility.

Rollback is additive: stop calling the write method and remove the new migration only
before deployment. Existing FileOS, Email, DataCore search and FOS-Master are unchanged.
