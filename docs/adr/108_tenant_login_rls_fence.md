# ADR-108 — Opt-in tenant-login fence for forced RLS

Status: accepted for synthetic implementation, 2026-09-25. This is an incremental
containment path for issue #7, not a claim that the existing shared runtime login
is safe against arbitrary SQL or that hosted multi-tenancy is accepted.

## Problem

The current runtime uses one database login and sets `email_brain.tenant_id` in a
transaction. A holder of that login with arbitrary SQL can forge the setting and
pass the existing permissive tenant policies. The exact identity resolver from
ADR-106 stops table-wide identity enumeration but does not bind database access to
the verified tenant. Every existing tenant-owned RLS table is `FORCE`d, but the
policy input is still caller-settable.

## Decision

Add a DBA-owned mapping from a database login (`session_user`) to exactly one tenant,
plus a no-login marker role. A privileged provisioning helper atomically checks the
login, grants the existing runtime privileges, records the mapping and grants marker
membership without inheritance, role switching or administration rights. A fixed,
schema-qualified `SECURITY DEFINER` predicate checks a row's
tenant against that mapping. It treats a marker member without a mapping as denied,
including after a mapping is removed. A mapped login remains fenced even if marker
membership is later removed. Ordinary unregistered shared logins keep their
current behavior so this migration does not silently break existing deployments;
they remain unsuitable for a hosted multi-tenant claim.
Binding UPDATE is refused; INSERT and DELETE are audited with the connecting DBA
login, and a removed role name cannot be enrolled again through the helper.

Install an `AS RESTRICTIVE` policy on every currently forced-RLS tenant table,
including the special `tenants.id` table. Restrictive policies are ANDed with the
existing permissive policies, so neither a forged tenant GUC nor an added
permissive policy can widen a mapped login's rows. The mapping table has no runtime
grants and no permissive RLS policy. New tenant tables must receive the fence before
runtime grants; the provisioning helper and regression test inventory fail closed
if the current table set is incomplete. Do not change historical migrations.

The predicate uses `session_user`, not `current_user`: `SET ROLE` changes the latter
but not the connecting login. Only a superuser can impersonate another session
user; superuser/BYPASSRLS and table ownership are forbidden for runtime logins.
The function has a fixed trusted search path and no dynamic SQL. It accepts only a
candidate row tenant and returns a boolean; it does not reveal the mapping table.
The two runtime-callable `SECURITY DEFINER` functions that can bypass table RLS,
`resolve_external_identity` and `lock_recovery_owners`, also apply this predicate
before returning a cross-tenant identity or locking a GUC-selected account.
Their existing execution grants and arguments are preserved.

## Verification and rollout

Use two fictional tenants and a real non-superuser login. Prove same-tenant reads
and writes, wrong-tenant reads/writes and definer-function results under forged `email_brain.*` settings,
`SET ROLE` attempts, mapping drift, and stolen single-tenant DSN behavior. Enumerate
every forced-RLS tenant table and its restrictive policy; run full PostgreSQL,
restore, and strict-runtime gates. A tenant-specific API/worker DSN router,
credential rotation and retirement of the shared data role remain separate work.
No external identity is obtained from a GUC.

This migration is forward-only. If it fails, stop using tenant-specific logins,
revoke their `CONNECT`/runtime grants and restore from a reviewed backup; do not
drop policies or mapping while such credentials remain live. Existing shared
runtime behavior and FOS-Master are unchanged by this tranche.
