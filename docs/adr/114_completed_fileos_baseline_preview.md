# ADR-114 — Bind donor-policy preview to a completed FileOS baseline

Status: accepted for private, nonpublishing synthetic comparison only.

## Context

ADR-113 validates a caller-supplied snapshot v1 before comparing it with a
donor-policy candidate. A valid manifest file does not prove that DataCore
imported and completed that exact run, nor that it is still the latest completed
run. Basing a policy transition on an uncommitted or stale file would be unsafe.

## Decision

- Add a read-scoped DataCore verifier for a v1 manifest and run UUID. It requires
  the latest completed receipt for that source to match the exact run, observed
  time, canonical manifest hash, inventory-policy hash, physical-root binding
  and item count. It also checks the source's current root binding, imported
  request receipt, every completed item/version identity, and the terminal
  outcome balance against the supplied manifest and completion receipt.
- Add a separate completed-baseline transition entry point. Verify before the
  donor scan and again afterward. A newer completion during the scan fails
  closed. Retain and recheck the exact manifest digest so in-process mutation
  also fails closed. Do not hold a database transaction across source I/O.
- Return only a private, nonpublishing preview with the completed run identity,
  completion time and manifest hash. Keep `publishable: false`, require review,
  and never infer deletion across the v1/donor policy boundary.
- Do not alter existing v1 publication, completion, absence events, search,
  Brain API, source files or FOS-Master. This verifier is not a v2 baseline
  transaction or authorization to publish.

## Verification

Unit tests cover the pre/post check order, stale-result and manifest-mutation
refusal. A real
PostgreSQL test covers missing completion, imported-only state, exact completed
receipt/item matching, read-scope enforcement, tampered policy, wrong run,
newer completion during scan and refusal before scanning a stale baseline.
Pinned-donor parity and full hosted CI/restore remain merge gates.

## Remaining gate and rollback

The second check proves the baseline was latest at check time, not that it
cannot change after the preview returns. Persisted v2 semantics need an
owner-reviewed transaction, metadata-only row model, absence suppression,
rollback, cloud-placeholder/platform shadow and bounded cohort acceptance.
Rollback of this additive read path is code-only; it creates no publication
or source state.
