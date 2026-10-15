# ADR-251 — Nonpublishing consecutive FileOS v2 observation preview

Status: accepted for synthetic, read-only policy evaluation only. No v2 run,
current read, absence event, FileOS effect or FOS-Master cutover is authorized.

## Context

ADR-124 seals one historical v2 baseline, but its staged membership cannot be
compared with a later donor-policy observation by the v1 completion path. That
path compares v1 policy receipts and can infer absence; a deferred cloud
placeholder, exclusion, unreadable area or changed policy must not become a
deletion claim. The first v2 baseline also has no later-run ledger yet.

## Decision

1. Add a pure, bounded preview over two closed FileOS donor candidates. Both
   must pass the existing exact v2 row validator, have the same source, physical
   root binding and donor policy, and have strictly increasing observations.
   This does not prove there was no intervening observation.
   The prior observation must have no scan errors. This function does not claim
   either candidate is an authorized or completed database run.
2. Classify each previously hashed row as unchanged, changed, deferred,
   excluded, error-covered, unobserved or an **absence candidate**. Separately
   classify a previous hashless row that becomes hashed; it has no prior
   version and can never yield an absence candidate.
   A current scan error anywhere suppresses all otherwise possible absence
   candidates. Exact file exclusions/errors and ancestor directory
   exclusions/errors cover a prior path; unrelated leaf errors do not.
3. Report current-only hashed/deferred counts, explicit blocker codes and the
   donor-equivalent mass-loss threshold over previously hashed rows. Return
   `publishable=false`,
   `absence_authorized=false` and `requires_review=true` even for an apparently
   clean run. A candidate is an observation to investigate, not proof that a
   source item should be hidden, deleted or written to an absence ledger.
4. Keep this an offline/private library operation. It reads no filesystem or
   database itself, has no API/CLI/worker route and changes no existing v1/v2
   table or FOS-Master file. A later ADR must bind a preview to an actual
   completed v2 baseline, fresh no-follow scan, immutable later-run ledger,
   tenant/source locks and current/rollback policy before any publication.

## Verification and rollback

Use fictional trees and closed candidate fixtures for unchanged, changed,
new, missing, deferred, exclusion, symlink/unreadable and mass-loss cases;
reject source/root/policy/time mismatches and malformed rows. Prove no source
or database mutation. Rollback removes only this preview and its tests; no
stored state or source effect exists.
