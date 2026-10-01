# ADR-124 — Complete one owner-authorized FileOS v2 baseline

Status: accepted for synthetic/disposable completion only.

## Context

ADR-123 supplies an explicit owner authorization bound to a reviewed stage and
prepared DataCore evidence, but it does not prove that the filesystem still
matches those rows. The v1 completion path cannot be reused: it requires the
v1 inventory policy, has no hashless donor observations, and would infer
absence across a policy boundary. A completed v2 baseline needs a durable
identity without silently changing current reads or FOS-Master operation.

## Decision

- Add a private, worker-only `brain.fileos.transition.complete` operation,
  additionally requiring `brain.source.ingest` and `brain.changes.read`.
  There is no REST, assistant, CLI, scheduler, or source-effect route.
- In one transaction under the existing per-source completion lock, recheck
  the exact current v1 receipt, stage/packet/plan, owner authorization,
  preparation, mapped hashed evidence and source root. Take a new bounded,
  no-follow donor-policy scan **after** preparation; require the policy,
  four count fields and every staged row to match exactly. Errors refuse
  completion. Deferred/excluded rows stay explicit and hashless.
- Seal one immutable, forced-RLS, tenant-login-fenced v2 baseline receipt per
  source, bound by composite foreign keys to the exact authorization,
  preparation and staged inventory. The receipt records the fresh observation,
  row digest, policy digest, counts and canonical completion digest. The
  immutable staged rows and prepared-row mapping are its membership ledger;
  a second row copy would create an avoidable divergence. A source-locked SQL
  trigger independently refuses an already-stale v1 baseline, mismatched
  counts, missing prepared evidence, or scan errors. Exact-ID replay is
  idempotent and rescans; alternate identity refuses. Audit only opaque IDs.
- A private, `brain.changes.read`-scoped compact inspection returns the
  completion identity, counts, observation and read-time latest-v1 match.
  It omits locators, root/policy digests and content, and explicitly reports
  current-read and absence authority as false. A stale historical baseline
  remains inspectable but cannot be mistaken for active freshness.
- This is a **historically complete private v2 baseline**, not activation.
  It does not update `current_version_id`, v1 run receipts, freshness,
  change feed, absence, search, active index or FileOS source files. A
  separate decision must define v2 current visibility, later v2 runs,
  absence suppression across the policy boundary, rollback, live-root
  acceptance and FOS-Master cutover.

## Verification and rollback

Use disposable PostgreSQL and synthetic roots for exact completion/replay,
source mutation, added/removed/deferred/excluded rows, wrong root/policy,
stale v1, missing or changed authorization, tenant/client/scope denial,
direct-SQL constraints, immutability, truncation, no-current-publication and
3,000-row stress. Run full CI, strict runtime, populated restore and pinned
donor parity. Rollback stops the private completer and leaves the historical
receipt/evidence intact; v1 reads and FOS-Master remain authoritative.
