# ADR-113 — Read-only v1-to-donor policy transition preview

Status: accepted for synthetic, nonpublishing comparison only.

## Context

ADR-112 creates a source-bound donor-policy candidate, but current FileOS
publication and completion accept only snapshot v1. A policy change causes
completion to refuse consecutive-run absence inference. Comparing a v1 receipt
with the donor candidate by item count alone could mistake an exclusion,
hashless placeholder, scan failure or policy gap for deletion.

## Decision

- Add a private, read-only preview taking a validated v1 snapshot and a fresh
  donor-policy scan of the same source and physical root. Require the donor
  observation to be newer than the v1 observation. It must perform no intake,
  database write, source mutation, evidence publication or absence event.
- Classify every prior v1 item as unchanged hash, changed hash, deferred,
  excluded, scan-error-covered or unobserved. Classify donor-only hashed items
  separately. A prior item not in the donor candidate is **unobserved**, never
  deleted. Metadata-only `no_hash`, dataless and oversize rows never acquire
  version/evidence identities.
- Keep the result `publishable: false` and `requires_review: true` even when
  there are no differences. Counts and explicit blockers aid review; they are
  not a switch authorization. Any root/source mismatch or non-new observation
  is a hard refusal. Any candidate error or unresolved prior item is a blocker.
- Preserve v1's policy hash and root binding in the report. Do not change the
  v1 snapshot, importer, completion, database, search, Brain API, operator or
  FOS-Master. A separate ADR must define v2 persistence, baseline transition,
  rollback, production shadow and owner acceptance before publication changes.

## Verification

Synthetic tests cover stable and changed hashes, donor-only items, v1 items
excluded/deferred/unobserved under donor policy, root/source/time mismatch,
symlink/error coverage and no source effects. The pinned-donor parity harness
remains the authority for the candidate's policy behavior. Local tests do not
replace hosted PostgreSQL/container/restore checks; branch merge is held if
GitHub Actions cannot execute.

## Rollback

Remove this additive preview and its tests. It has no persisted state or
source effects, so no data rollback is required.
