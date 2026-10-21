# ADR-253 — Immutable private FileOS v2 later-observation packet

Status: accepted for synthetic/disposable, nonpublishing implementation only.
This is a durable review packet, **not** a completed later run, absence event,
current v2 read, live-root approval or FOS-Master cutover.

## Context

ADR-252 checks a fresh donor-policy observation against one completed,
owner-authorized v2 baseline, but returns only an ephemeral summary. A reviewer
cannot compare repeated observations or investigate a fault after the process
exits. The baseline table is one-per-source and must not be repurposed for
later runs; the v1 completion/absence tables use a different policy.

## Decision

1. Add one append-only, forced-RLS, tenant-login-fenced packet table linked
   by tenant/source/completion identity to the exact v2 baseline. The packet
   contains the closed fresh donor candidate and ADR-251 classification,
   their canonical digests, fixed count maps, blocker codes, observation time
   and root/policy binding. Cap canonical UTF-8 payload at 16 MiB. A source-
   locked SQL insert guard checks the completion, current v1 basis and source
   root binding; SQL also fixes `publishable=false`,
   `absence_authorized=false` and `requires_review=true`. Row mutation and
   truncation are refused. No current/absence query reads this table.
2. A private worker with `brain.fileos.transition.verify`,
   `brain.changes.read` and `brain.source.ingest` may record a packet. Recheck
   the complete stored stage and completion, scan the explicitly bound root
   under the source lock, apply the pure classifier and seal one exact request
   UUID. Exact-ID replay is historical and does not claim a fresh scan;
   alternate identities create separate observations. Reject a different
   actor/completion for the same ID. There is no CLI, scheduler or assistant
   write route.
3. A separate private read requires `brain.changes.read` and verifies the
   stored canonical digest and closed candidate/preview relationship. It
   returns only opaque IDs, observation, count maps, blocker codes and a
   digest—never locators, content or the root path. Fixed-code audit is allowed.
4. Do not prepare new evidence, publish documents, create an absence event,
   advance freshness, activate a generation or modify FOS-Master. A later
   decision must convert reviewed observations into an exact immutable
   per-row later-run ledger with processing outcomes and rollback semantics
   before any v2 current authority.

## Verification and rollback

On disposable PostgreSQL and fictional roots prove record/read/replay,
multiple later observations, missing/deferred/error rows, wrong root,
stale v1, scope and tenant denial, direct SQL count/authority mismatch,
immutability/truncation and no current/absence effect. Run full local and
hosted gates. Rollback stops packet writes and retains historical rows; no
source or current-state rollback is needed.
