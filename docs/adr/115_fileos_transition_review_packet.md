# ADR-115 — Seal a private FileOS donor-policy review packet

Status: accepted for nonpublishing, synthetic/disposable review only.

## Context

ADR-114 verifies an exact latest completed v1 run before and after a donor-policy
scan, but its returned preview is ephemeral. A later reviewer needs to inspect
the candidate observation and comparison together without treating either as a
v2 baseline or deletion evidence. Repeating the scan could observe different
files and yield a misleading pairing.

## Decision

- Scan once and retain the candidate and its preview in one bounded packet.
  Bind it to the v1 source, run UUID, canonical manifest digest, completion time,
  inventory policy and physical-root digest. The packet is private and always
  `publishable: false`, `requires_review: true`.
- Require both source-ingest and change-read scopes to record it. Recheck the
  latest exact completed v1 receipt under the same per-source advisory lock as
  completion before insertion. A newer completion makes the packet stale.
- Persist in an append-only, forced-RLS table with tenant-login fencing, an
  exact completed-receipt foreign key, idempotent packet-ID replay, a canonical
  SHA-256 digest and a 16 MiB packet bound. Reject malformed ledger counts and
  invented identities on deferred observations. Deny UPDATE, DELETE and
  TRUNCATE, including through the runtime role.
- Keep this an internal operator library path. There is no CLI or Brain API
  route and no consumer in current search, freshness, absence, publication or
  FileOS completion. The table is a review artifact, not a trusted proof that
  the filesystem was unchanged after scanning.
- Leave snapshot v1, source files and FOS-Master unchanged. Never interpret an
  unobserved or donor-excluded prior item as a deletion across this boundary.

## Verification and remaining gate

Unit tests check one scan and hashless metadata-only rows. Disposable PostgreSQL
tests cover exact-run binding, replay, duplicate/tampered packet refusal, size
bound, stale baseline, immutability and nonpublication. Full CI, strict-runtime,
populated restore and donor parity are required before merging.

This does **not** establish v2 row semantics, transition approval, rollback,
cloud-placeholder behavior, live-root acceptance or cutover. A future v2
publication ADR must explicitly define those gates and must not infer authority
from this packet alone. Rollback of this additive review path is to stop its
writer; retained packets remain immutable for provenance.
