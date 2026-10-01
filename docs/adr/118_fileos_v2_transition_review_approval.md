# ADR-118 — Bind an owner's review to an exact FileOS v2 transition plan

Status: accepted for synthetic/disposable review only.

## Context

ADR-117 stores a donor-shaped inventory without publishing it. A staged ledger
can contain v1 exclusions, deferred/hashless observations and donor-only files.
Its mere existence is not permission to treat those differences as deletion or
to start a v2 completed run. A later baseline transaction needs an explicit,
auditable human decision bound to the exact packet, stage, latest v1 receipt and
classification counts—not a free-form approval flag.

## Decision

- Add a private, content-free transition-plan read. Under the per-source
  completion lock, recheck the packet's canonical digest, candidate digest,
  exact relational staged rows, prior completed receipt and root binding.
  Return only opaque identities, counts, fixed blocker codes and a canonical
  plan SHA-256. No locator or content enters the response or audit event.
- A plan with a prior snapshot error, donor scan error, unobserved or
  error-covered prior item cannot be approved. Changed content is visible in
  counts but must be revalidated before later publication. Deferred and
  excluded observations are not deletion evidence.
- Add a distinct `brain.fileos.transition.review` scope that bootstrap
  credentials may grant only to human principals. Approval additionally
  requires `brain.evidence.read` and current owner membership. The caller must
  supply the exact plan digest and acknowledge both complete count maps.
- Persist one append-only, forced-RLS, tenant-login-fenced approval receipt per
  stage. Bind its stage, packet/candidate digests, prior run, plan digest,
  acknowledged counts, actor and time. Same-ID replay is idempotent; changed
  or alternate-ID replay is refused. Refuse stale plans under the source lock.
- Keep this an internal library path. It is not a Brain API/assistant route,
  v2 publication, live-source approval, FOS-Master switch or source effect.
  A future ADR must define the actual v1-to-v2 baseline transaction, fresh
  source revalidation, v2 freshness/absence semantics and rollback. That
  transaction must independently recheck the approval and current source;
  possession of this receipt alone is insufficient.

## Verification and rollback

Use synthetic unit and disposable PostgreSQL tests for human/scope denial,
exact-count and digest matching, hard blockers, stale v1 receipt, replay,
tenant isolation, immutability and nonpublication. Run full CI, strict runtime,
populated restore and pinned-donor parity before merge. Rollback stops the
approval writer; immutable historical receipts remain private and have no
runtime consumer.
