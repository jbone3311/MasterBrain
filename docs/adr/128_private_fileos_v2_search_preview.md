# ADR-128 — Private FileOS v2 search comparison

Status: accepted for synthetic/disposable implementation; no v2 activation.

## Context

ADR-126 permits an immutable, ready FileOS v2 generation in the shared DataCore
index, but PostgreSQL forbids making it current. The owner needs to inspect
whether its bounded lexical results behave as expected before any separate
current-visibility decision. Querying its chunks through an ordinary Brain API
route would incorrectly imply that the v2 baseline is current.

## Decision

- Add a private, read-only reviewer method, not a public API or model tool. It
  requires a human principal with `brain.fileos.transition.review`,
  `brain.search`, and `brain.evidence.read`. The caller names one source, one
  ready v2 generation and one bounded query. It never selects a generation by
  an ambiguous "latest" alias.
- In one tenant-scoped transaction, take the FileOS source advisory lock and
  verify the generation's exact v2 completion, ready attempt, source and root
  binding against the latest completed v1 run. A stale baseline fails closed.
  The currently activated v1 generation is captured in the same transaction;
  if none exists, report that explicitly rather than fabricating a comparison.
- Use the same lexical SQL, ranking, excerpt and result limit for each named
  generation. Keep the two result groups and ranks separate. Label v2 results
  `historical_preview`, never `current`. The returned information is not a
  freshness attestation about files on disk after the v2 completion.
- Record a content-free audit event. No source state, activation, absence or
  approval receipt changes. Do not expose preview results through normal
  current-search, `/brain`, or external assistants.

## Acceptance and rollback

Synthetic PostgreSQL tests cover ready result membership, an absent active v1
generation, denied worker/scope/other tenant, wrong source or generation, stale
v1 baseline, bounds, and unchanged current state. Stress the query over the
existing 3,000-row synthetic v2 corpus. Run full local and hosted gates. A
later ADR must define current policy, subsequent v2 runs, absence, rollback,
and explicit owner acceptance before v2 activation can be considered.

Rollback removes this private read method; historical access-audit events
remain, but no source/index state needs reversal. FOS-Master and v1 active
search remain operational and unchanged.
