# ADR-123 — Explicit owner authorization for a FileOS v2 baseline

Status: accepted for synthetic/disposable authorization only.

## Context

ADR-118 records an owner's review of a staged policy comparison. ADR-119 verifies
that a later scan still matches it, and ADR-121 prepares shared evidence after a
third scan. None is permission to complete or expose a v2 baseline. The distinction
matters because deferred and excluded observations, and a changed inventory policy,
must never silently become absence or current-search decisions.

## Decision

- Add a separate, private, human-only `brain.fileos.transition.authorize` scope.
  Authorization also requires `brain.evidence.read`, current owner membership,
  the exact plan digest, preparation digest, and both acknowledged count maps.
  There is no REST, assistant, CLI, scheduler, or filesystem-write route.
- Under the source completion lock, revalidate the sealed stage and latest exact
  v1 receipt, existing review, verification, preparation digest, and prepared
  evidence ledger. A changed v1 run or mismatched identity refuses authorization.
- Record one immutable, tenant-scoped authorization receipt per stage, bound by
  a composite foreign key to the exact preparation. Same-ID, same-actor replay
  is idempotent; alternate identity or changed input refuses. Forced RLS,
  tenant-login fence, protected truncation and audit apply.
- This receipt authorizes only a future, separately specified v2 baseline
  completion attempt. It is **not** a fresh filesystem attestation, completed
  baseline, read switch, absence inference, index activation, source effect, or
  FOS-Master cutover. Completion must rescan, recheck this receipt and current
  v1 state under the source lock; a new ADR must define its ledger, visibility,
  rollback and SQL invariants. No live-source authorization is conveyed.

## Verification and rollback

Test exact replay, changed/stale plan, missing preparation, wrong client/scope,
cross-tenant denial, immutable/RLS/SQL linkage and unchanged current reads on a
disposable database. Run full CI, strict runtime and populated restore. Rollback
stops the private authorization call; retain its receipt and prepared evidence,
leave v1 and FOS-Master operational, and do not down-migrate protected data.
