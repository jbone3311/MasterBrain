# ADR-086 — Seal document batches and preserve both worker boundaries

Status: accepted and implemented in `87ea0d0`.

## Context

The private archive-document preview makes reviewed selection practical. Repeating
one-document commands manually makes uncertain retry and partial progress difficult to
audit, while executing preview results directly would collapse observation into
automatic two-worker fan-out.

## Decision

Accept only an owner-private canonical plan for one inventory, one code revision and
1–100 unique ordered locator/expected-format/idempotency-key triples. Require exact
suffix/format agreement and the plan digest before database or worker access. Execute
sequentially through the existing document selector, two restricted workers and
publication contract, reauthenticating at every sensitive boundary. Stop at the first
refusal and support progress only through exact unchanged-plan replay.

Return indexes and counts, never locators, formats or extracted metadata. Preserve
completed append-only derivatives; current-parent fences continue to control current
search visibility.

## Alternatives rejected

- Execute a preview page: preview is observation, not sealed mutation intent.
- Infer rather than seal the expected format: weakens operator review and drift
  detection at the worker boundary.
- Generate keys inside the executor: uncertain retries could duplicate intent.
- Skip failures or run in parallel: obscures gaps and violates fail-stop ordering.
- Merge the two workers: broadens each sandbox's authority and weakens isolation.
- Hold one database transaction across workers: external execution cannot be made
  atomic and would retain locks across expensive processing.

## Rollback

Remove the document-batch plan, controller and command. Existing one-document
publication, preview, current search and retained evidence remain unchanged.
