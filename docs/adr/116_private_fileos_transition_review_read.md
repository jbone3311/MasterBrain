# ADR-116 — Bounded private reads of FileOS transition evidence

Status: accepted for private, synthetic/disposable review only.

## Context

ADR-115 seals a candidate and its completed-v1 comparison, but provides no
supported way to inspect the packet later. Ad hoc SQL risks disclosing the
private locator ledger and makes it easy to mistake an old packet for a current
transition proposal. Review must be possible without granting publication.

## Decision

- Add one internal DataCore read method for a packet UUID. `brain.changes.read`
  permits a compact summary containing only identities, counts, fixed blocker
  codes, timestamps and the canonical packet digest. It does not return paths,
  filenames, content, root digests or the full packet.
- Locator-level detail additionally requires `brain.evidence.read` and is
  returned in immutable, ordinal pages of at most 50 fixed-shape rows. Pages
  distinguish prior-v1 classifications from donor hashed, deferred, excluded
  and error ledgers. Hashless rows still have no digest or version identity.
- Recompute the canonical packet digest when reading and fail closed on a
  mismatch. Under the source completion lock, report only whether the latest
  completed receipt still matches the packet's v1 identity. This is a status
  observed at read time, not a reservation, a new baseline verification, or an
  approval. Historical packets remain readable when superseded.
- Audit each successful read with an opaque packet ID. Do not expose this
  operation as a Brain API route, assistant tool or general SQL endpoint. Do
  not change snapshot v1, search, freshness, absence, source files or FOS-Master.

## Verification and rollback

Use fictional PostgreSQL fixtures to test summary redaction, extra detail
scope, stable pagination, stale-run status, wrong-tenant invisibility and
digest-tamper refusal. Run full CI, strict runtime, restore and pinned-donor
parity before merge. Rollback stops the additive reader; immutable packets and
all v1 behavior remain intact. This read path does not define metadata-only v2
publication, transition approval, rollback from v2 or FileOS cutover.
