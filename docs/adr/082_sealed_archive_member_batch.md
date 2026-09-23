# ADR-082 — Seal archive-member batches and stop on first refusal

Status: accepted and implemented in `1a3fd58`.

## Context

The private preview makes reviewed member selection practical, but executing many
independent commands makes crash recovery and operator intent hard to audit. Letting an
executor discover members or allocate keys would collapse planning and mutation into
automatic archive fan-out.

## Decision

Accept only an owner-private canonical plan for one inventory, one code revision and
1–100 unique ordered locator/key pairs. Require the exact plan digest before database
access. Execute sequentially through the existing one-member select/read/normalize/
publish contracts, reauthenticating at every sensitive boundary. Stop at the first
refusal and support progress only through exact unchanged-plan retry.

Return item indexes and counts, not locators or content. Preserve already-completed
append-only derivatives and let current-parent fences control search visibility.

## Alternatives rejected

- Execute a preview page directly: preview is mutable operator observation, not sealed
  intent, and contains no stable keys.
- Generate keys inside the executor: uncertain retry could duplicate intent.
- Skip failed members and continue: hides gaps and weakens reviewed ordering.
- Parallel execution: complicates fail-stop boundaries and source-change races.
- One transaction for worker reads and all writes: holds database locks across isolated
  processing and cannot make external worker execution atomic.

## Rollback

Remove the batch plan/controller/command. One-member publication, existing derivatives,
preview and current/retained search remain valid and unchanged.
