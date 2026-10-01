# ADR-119 — Verify an approved FileOS v2 baseline against a fresh source scan

Status: accepted for synthetic/disposable verification only.

## Context

ADR-118 records a human decision about one immutable FileOS v2 stage, but its
candidate was scanned earlier. Source files can change after approval, and a
database source lock does not lock the filesystem. Moreover, v1 completion
explicitly refuses a policy change and the staged v2 rows are not yet shared
evidence versions. Treating approval alone as a v2 completed run would create
false freshness, disappearance and search claims.

## Decision

- Introduce a distinct private `brain.fileos.transition.verify` worker scope.
  Bootstrap credentials may grant it only to a worker. Verification also
  requires `brain.changes.read` and current owner membership. It has no REST,
  assistant or general filesystem-browsing route.
- Under the source completion lock and one database transaction, re-evaluate
  the exact approved plan, its stage/packet/row digests and latest completed
  v1 receipt. A changed, stale or hard-blocked plan refuses verification.
- Perform one fresh, bounded, no-follow donor-policy scan of the explicitly
  supplied root using the same metadata-only setting and pinned donor policy.
  Require the physical-root binding, policy, four count fields and every
  projected staged row (including deferred/excluded/error reasons) to match
  the approved stage exactly. Any new scan error or mismatch fails closed.
  The database observation time must be strictly after the staged observation.
- Persist one append-only, forced-RLS, tenant-login-fenced verification receipt
  per source and stage. Bind it to the approval, stage, packet/candidate/plan
  digests, source, prior v1 run, fresh observation time and exact row/count
  digest. A same-ID exact replay is idempotent; an alternate identity or changed
  source fails. Audit only opaque identities and fixed event codes.
- The receipt proves that a scan matched the approved stage **at its recorded
  observation**, not that the filesystem remains unchanged. It is not a v2
  completed run or current freshness, absence, index, search, deletion or
  FileOS cutover authority. v1 operation and FOS-Master remain unchanged.
  A later ADR must define v2 evidence intake, completion, visibility, policy
  activation, consecutive-run absence and rollback, with a fresh check at
  that boundary. The same root must not be trusted indefinitely from this
  receipt.

## Verification and rollback

Use synthetic/disposable PostgreSQL tests for exact-match verification,
changed bytes, added/removed/deferred/excluded rows, root drift, newer v1
completion, unapproved or blocked stages, wrong client/scope/tenant, replay,
immutability and nonpublication. Run the full CI, strict runtime, populated
restore and pinned-donor parity gates. Rollback stops this private writer;
historical receipts remain immutable and unused by current reads. The
database scan transaction may hold the source lock for the bounded scan;
future live operation requires a measured latency and concurrency budget.
