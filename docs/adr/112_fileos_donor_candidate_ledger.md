# ADR-112 — Source-bound FileOS donor-policy candidate ledger

Status: accepted for synthetic, nonpublishing migration verification only.

## Context

The pinned FOS-Master scanner catalogs regular files above 2 GiB, dataless
placeholders and explicit no-hash scans with a null digest. MasterBrain's v1
source-version/evidence contract requires a verified SHA-256. Treating a null
donor digest as a published source version would invent evidence; silently
dropping the locator could later look like deletion. ADR-111/ DC-002H provide
root-confined donor-policy observations, but their flat rows are not yet a
source-bound migration contract.

## Decision

- Build a separate versioned candidate from one bounded shadow observation,
  one validated FileOS source ID and one timezone-aware observation time.
  Preserve the shadow's donor classifier, 2 GiB hash boundary, no-follow safety,
  exclusions and reason-coded errors. Record the private physical-root binding.
- Hashed rows receive stable source item/version identities, a valid SHA-256,
  size and media type. This is a candidate identity only, not a persisted
  evidence receipt. Metadata-only `no_hash`, `dataless` and `oversize` rows
  receive a stable item ID and explicit deferred reason, but **no version ID,
  digest, evidence ID, document or searchable text**.
- Require exact counts, sorted unique locators, disjoint hashed/deferred/error/
  exclusion ledgers and a fail-loud record bound. Keep the object explicitly
  `publishable: false` with a candidate-version marker that v1 intake and
  completion reject. Errors or deferred rows cannot be relabeled as complete.
- Do not change `snapshot_tree` v1, the private publisher, policy SHA, SQL,
  Brain API, FOS-Master or the current-search path. A later ADR must define a
  publishable v2 manifest, metadata-only persistence/freshness semantics,
  v1-to-v2 baseline transition, rollback and owner acceptance.

## Verification

Use only fictional temporary roots and the pinned donor scanner in isolated
in-memory SQLite. Assert exact ordinary membership/size/SHA, replay and one
change; prove that metadata-only/dataless/oversize entries never gain a version
or digest, and that the candidate is refused by the v1 importer. Test duplicate,
overlapping, malformed, root-drift and no-follow failures. Run full CI, the
restricted-worker gate and populated restore before merging. Hosted CI without
the donor checkout cannot replace the local pinned-donor comparison.

## Rollback

Remove this additive candidate module and comparator/tests. No source files,
database rows, v1 policy or donor state need restoration.
