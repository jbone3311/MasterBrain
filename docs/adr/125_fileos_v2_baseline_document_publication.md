# ADR-125 — Publish and account for v2 baseline documents before activation

Status: accepted for synthetic/disposable implementation; no current-read activation.

## Context

ADR-124 seals an owner-authorized, freshly matched FileOS v2 inventory, but its
prepared hashed source versions have no normalized documents or index generation.
An activation that merely points current search at the completed inventory would
either return no content or accidentally reuse v1 derivatives whose version and
policy identity differ. Hashless, excluded and unsupported observations must not
be promoted into fabricated searchable content. FOS-Master remains the unchanged
operational donor at `218d5caec2f20b9047fd3eb8e027dc671acf0c15`.

## Decision

- Add a private worker-only v2 document-publication operation requiring a new
  `brain.fileos.transition.publish` scope, `brain.document.publish` and
  `brain.changes.read`. It consumes one completed v2 baseline, explicit root
  and code revision. There is no public/API/assistant route or scheduler.
- Load the immutable hashed staged rows and their exact prepared version/evidence
  mapping. Recheck completion digest, source root and latest v1 binding before
  work. For each hashed row, use the existing confined, size-bounded text or
  isolated PDF/Office extraction path; rehash the opened bytes against the
  staged SHA before publishing a normalized document on the **prepared v2
  version**. The existing deterministic chunker and provenance path is reused.
  No source file is written. A failed or changed read is accounted, never
  silently treated as an empty document. Before sealing the attempt, take a
  new exact donor-policy scan under the source lock and compare every row,
  policy, count and root to the completed baseline. Drift refuses the attempt;
  no earlier per-file hash is treated as continuing root attestation.
- Persist one append-only, forced-RLS, tenant-login-fenced publication outcome
  per hashed staged row and one final source-locked **attempt** receipt. A
  deferred database check balances the outcome ledger against the completion's
  hashed count and requires exact staged/prepared identities. `extracted`
  requires an exact normalized document/evidence link; other terminal outcomes
  require no document. Every hashed row is accounted; an attempt is `ready`
  only when no row is `changed` or `failed`. Hashless and excluded rows remain
  in the original staged ledger with explicit counts; they have no publication
  item, version, evidence or document.
- Retry of one attempt ID requires the same completion, root, code revision and
  processor identity; already published normalized documents/chunks replay
  through deterministic identities. A blocked attempt is durable and may be
  followed by a new attempt ID after repair, but at most one ready attempt may
  exist for a completed baseline. A process crash before the final receipt may
  leave historical immutable derivatives but cannot create current v2
  visibility or an incomplete ready receipt.
- This receipt establishes **document readiness**, not source freshness,
  index-generation readiness or activation. Existing v1 current pointers,
  active generations, absence, current-search routes and FOS-Master operation
  remain unchanged. Retained-history DataCore search and change feed may expose
  newly published v2 derivatives under their existing separately authorized
  semantics; callers must not label them current. A later ADR must define an
  exact v2 index generation, explicit owner activation, later v2 runs,
  cross-policy absence, rollback, live shadow and bounded cohort cutover.

## Verification and rollback

Use synthetic roots and disposable PostgreSQL for exact hashed/deferred/excluded
accounting, text and isolated-document results, changed bytes/root, unsupported
types, crash/replay, wrong tenant/client/scope, concurrent v1 completion,
direct-SQL forged/missing/late outcome rows, immutable/RLS/truncation checks,
bounded stress and no current-read effects. Run full CI, strict runtime,
populated restore and pinned donor parity. Rollback stops the private worker;
historical derivatives and receipts remain for audit while v1 and FOS-Master
continue to serve current reads.
