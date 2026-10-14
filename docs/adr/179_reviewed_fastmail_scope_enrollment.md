# ADR-179 — Reviewed private Fastmail scope enrollment and disconnect

Status: implemented for synthetic/disposable verification. No private mailbox
read, provider-token grant or live-source acceptance follows from this ADR.

## Problem

ADR-177 can pin an unused account and ADR-178 can operate only when that pin
already matches, but manual administrator SQL has no bounded, reviewable
enrollment or revocation path. A wrong tenant, account, source address or
window could otherwise be pinned by an operator outside the command contract.

## Decision

- Add a private, local administrator command with `check`, `enroll` and
  `disconnect` actions. Its closed, owner-only configuration names an exact
  version-2 `sync-read` configuration, expected tenant and owner actor, source
  address, and separate human owner credential/token files. The owner token
  must have a new human-only `email.source.manage` scope and an active owner
  membership in that tenant. The worker credential must have exactly
  `email.ingest` and match that same tenant. This is an opt-in bootstrap
  authority, not a hosted issuer or general Brain API permission.
- `check` validates private files, identities, exact scope fingerprint and
  administrator-visible SQL state without creating a row, lease, cursor or
  provider client. It returns bounded, content-free state and fingerprint;
  the owner must inspect the private config itself before approving.
- `enroll` requires explicit account UUID, scope fingerprint and full binding
  digest confirmations. The digest binds tenant, owner actor, address, account,
  provider account ID, secret reference and exact scope, so changing any of
  those fields after `check` invalidates the reviewed action.
  It inserts a **new** Fastmail account atomically with its provider account
  ID, secret reference and ADR-177 pin. It refuses an existing account or
  duplicate address rather than repurposing an unscoped source. It inserts a
  content-free audit event in the same transaction. No token is stored in SQL;
  the command never contacts Fastmail or starts a worker.
- `disconnect` requires the same confirmations and exact existing account
  binding. It serializes with the account's worker/ingest advisory lock,
  changes only `status` to `disconnected`, keeps the scope pin and all evidence,
  and records an audit event. A repeated exact disconnect is a no-op. It does
  not revoke the provider token, purge evidence, hide historical search or
  authorize future reactivation. An in-flight HTTP request may finish, but a
  subsequent guarded request or page publication must fail after disconnect.
- Administrator DSN stays in the process environment, never the private config
  or output. Generic errors omit source address, token, provider ID and SQL
  details. There is no remote endpoint, model tool or runtime account UPDATE.

## Proof and rollback

Use fictional credentials and disposable PostgreSQL. Tests must cover no-write
check, exact atomic insert and `sync-read --check`, post-check binding drift,
wrong human/worker tenant,
nonowner/assistant/worker management denial, missing/mismatched confirmations,
existing account/address refusal, cross-tenant disconnect denial, retained pin
and evidence, idempotent disconnect, concurrent worker publication refusal and
content-free audit/output. Full CI, strict-runtime and restore gates apply.
Rollback stops the command and any scoped worker, then disconnects the source
with owner review; do not down-migrate, unpin a used account or delete retained
evidence. Provider-token revocation remains a separate Fastmail action for an
immediate outbound-access cutoff. Real-provider acceptance requires a separate
owner decision and disposable live-source plan.
