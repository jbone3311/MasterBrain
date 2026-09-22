# ADR-081 — Require a read-only archive-member preview before batch design

Status: accepted design; implementation pending.

## Context

The one-member command is intentionally explicit, but an owner needs a bounded way to
discover eligible virtual member locators before manually invoking it. Jumping directly
to archive-wide execution would combine discovery, key allocation and mutation while
making partial failure difficult to review.

## Decision

Add an owner-private, ordinal-cursor preview for one explicitly named current archive
inventory. Return only members eligible for the existing bounded text normalizer plus
their already-published label. Use the existing exact worker scopes and configuration,
but perform no source read, Docker invocation or write. Treat returned locators as
untrusted private metadata.

Do not authorize a batch schema or executor in this checkpoint. Any future batch must
be a separately reviewed, digest-bound plan with caller-supplied stable keys.

## Alternatives rejected

- Automatically publish every eligible member: grants unreviewed fan-out authority.
- Generate idempotency keys in preview: blurs read-only planning and execution intent.
- Return all unsupported/container members: increases metadata disclosure without
  helping the current text operation.
- Use a mutable offset cursor: unstable semantics and ambiguous retries.
- Add a public Brain API route: expands network exposure for an operator-only action.

## Rollback

Remove the preview store method, controller and command. Existing inventories,
one-member publication and current/retained search remain unchanged.

