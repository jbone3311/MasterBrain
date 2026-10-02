# ADR-132 — Administrator-owned OIDC Brain source grants

Status: accepted for synthetic/disposable implementation; hosted assistant acceptance remains open.

## Context

ADR-130 filters three Brain read routes by source, but only synthetic bootstrap
credentials can supply the allowlist. Verified OIDC identities are bound to
administrator-owned Email scopes and have no source enrollment. An authentic
token must not choose a source, and a saved request context must not survive a
grant change.

## Decision

- Extend the administrator-owned external-identity scope allowlist only with
  `brain.search`, `knowledge.search`, `brain.evidence.read` and
  `brain.content.read`. Assistant bindings combining one of these with legacy
  Email scopes are refused: those Email routes are not source-filtered. Other
  Brain/Knowledge routes remain unavailable to assistants under ADR-130.
- Store source enrollments in a separate, forced-RLS table keyed to the exact
  identity binding and an existing source in the **same tenant**. Only the
  dedicated identity-administrator role can add/remove grants. Enrollment is
  bounded to 20 distinct sources. The runtime and identity-only lookup logins
  cannot read or modify this table directly.
- Resolve the verified issuer/subject/client tuple through a new exact-key
  definer function that returns the active binding and its sorted source IDs.
  Keep the old resolver temporarily for rolling-version compatibility; new
  binaries require the new function. The result is server-owned context, never
  a token or request claim. A Brain-scoped assistant without a source grant
  cannot authenticate for Brain reads.
- Every grant add/removal increments the binding revision and writes a
  content-free administrative audit record. Every data transaction re-resolves
  the exact binding and compares identity, revision, scopes and source IDs.
  Revocation stops the next transaction and future API calls; an already
  admitted transaction is not retroactively cancelled. The three source-aware
  routes recheck during their existing database reads. No response cache or
  generated-answer store is introduced.
- Preserve human bootstrap reads, existing Email-only OIDC bindings, source
  ingestion and worker authority. This increment does not expose a public
  enrollment endpoint, grant original FileOS bytes, or modify FOS-Master.

## Acceptance and rollback

Use fake signed access tokens and a disposable PostgreSQL database. Show a
non-superuser identity administrator can enroll only same-tenant, existing
sources; cannot exceed the cap or mix Brain and legacy Email assistant scopes;
and leaves audit/revision evidence. Show a Brain-scoped assistant cannot read
before enrollment, sees only enrolled Email/FileOS evidence after enrollment,
and loses search/evidence/content on revocation, including a previously saved
context. Test another tenant, forged source context, limited-rank search, and
direct runtime/lookup-login table denial. Run migration, full tests, strict
runtime, populated restore and donor parity before merge.

Rollback is forward repair: stop the new API, revoke new Brain scopes and
source grants with administrator review, preserve migration/audit history, and
return only to a local Email-only configuration. Do not expose the older
resolver as a hosted Brain authorization path. Hosted issuer enrollment,
credential lifecycle, all-route source semantics, derived-cache revocation,
live data and a named assistant remain [issue #88](https://github.com/jbone3311/MasterBrain/issues/88).
