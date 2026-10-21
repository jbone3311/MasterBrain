# ADR-252 — Bind a later FileOS v2 preview to a completed baseline

Status: accepted for synthetic/disposable, private nonpublishing implementation.
This does not authorize a later completed run, absence event, current v2 read,
live root, FileOS effect or FOS-Master cutover.

## Context

ADR-251 compares two closed donor-policy observations but cannot tell whether
the first is a completed, owner-authorized baseline. ADR-124 has that baseline
and its immutable staged ledger. A later preview must not trust a caller's
candidate JSON or a stale v1 basis, and it must not expose locators through an
assistant or general API.

## Decision

1. Add a private worker-only operation taking an exact v2 completion ID and
   explicit local root. Require `brain.fileos.transition.verify` and
   `brain.changes.read`; no REST, CLI or scheduler route. Under the existing
   tenant/source advisory lock, recheck the complete stage/packet/row ledger,
   current v1 receipt, reviewability and completion digest. The stored packet's
   candidate, not caller data, is the prior observation.
2. Check the explicit root against the sealed physical-root binding, take a
   database-clock observation newer than the completed baseline, scan with the
   unchanged bounded no-follow donor candidate builder, then recheck the root
   binding. Apply ADR-251's pure classifier. A changed or unreadable root
   refuses the operation; scan coverage errors remain explicit blockers and
   never become absence candidates.
3. Return only opaque completion/source identity, observation times, fixed
   counts/blocker codes and a digest of the full ephemeral preview. Do not
   return locators, content or the root path. Audit a fixed operation code.
   The digest is not a persisted receipt or attestation of ongoing root state.
4. Do not persist a later-run ledger, advance source freshness, write absence
   events, activate a v2 generation or modify the donor. A separate ADR must
   define an immutable later-run transaction, exact per-row evidence mapping,
   source/current visibility, rollback and owner acceptance before cutover.

## Verification and rollback

Use a disposable tenant-fenced PostgreSQL database and fictional root. Prove
the completed baseline yields an unchanged preview, a subsequently missing
file is only a candidate, wrong root/identity/scope and newer v1 completion
refuse, and v1 current/absence tables remain unchanged. Recheck a mutated
source and the exact completion digest. Rollback removes only the private
operation and tests; no new schema or source data is created.
