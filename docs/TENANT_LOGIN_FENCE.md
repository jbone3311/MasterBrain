# Tenant-specific PostgreSQL login fence

Status: synthetic opt-in containment primitive under [ADR-108](adr/108_tenant_login_rls_fence.md).
Migration 0037 does **not** change the existing shared runtime login or close
[issue #7](https://github.com/jbone3311/MasterBrain/issues/7).

[ADR-109](adr/109_tenant_database_routing.md) adds an opt-in `email-brain serve
--tenant-db-config /absolute/private/routes.json` path. Its version-1 JSON has
`identity_dsn` and a `tenants` object keyed by canonical UUID, each value a
distinct explicit PostgreSQL DSN on the same database. The owner-only file must
be regular, no-follow, mode `0600` under a mode-`0700` owner directory outside
the checkout/synchronized folders. The lookup login has no public-table grants;
the DBA provisions it with `grant_identity_lookup(conn, role)`. That helper
explicitly grants only the exact resolver; ordinary PUBLIC function/catalog
privileges still apply. The service selects a tenant DSN *after* verified-token
identity resolution and checks its immutable login binding before tenant SQL.
Missing/wrong/shared routes fail closed. Never put these DSNs in Git or logs.

## Contract

`masterbrain_tenant_login_bindings` records one database login to one tenant. Only a
superuser DBA can call `grant_tenant_runtime(conn, role, tenant_id)` to provision an
already-created, safe, non-owner login. Provisioning grants the existing runtime
table/function privileges, binds the tenant, and grants marker membership without
inheritance, role switching or administration rights, in one transaction. It
refuses missing migration, a conflicting or previously removed binding, an
unsafe/inherited role or any
forced-RLS table missing the restrictive fence. The mapping table is not directly
readable or writable by runtime. Retargeting by UPDATE is refused; INSERT/DELETE
produce append-only audit events with the connecting database login. A removed
role name cannot be re-enrolled; rotate to a new login instead.

The restrictive RLS policy is added to every existing forced-RLS tenant table. For
an opted-in login, it checks the authenticated `session_user` against the DBA-owned
mapping in addition to the older caller-settable tenant GUC policy. Forging
`email_brain.tenant_id`, `email_brain.actor_id`, identity GUCs or using `SET ROLE`
cannot change the mapped tenant. An enrolled marker member with a missing mapping
gets no tenant rows; a mapping remains a fence even if marker membership is removed.
`tenants.id` uses the same rule as other tables' `tenant_id`.
The exact identity resolver and recovery-owner lock function are separately
fenced because their `SECURITY DEFINER` owners can bypass table RLS. A scoped
login cannot obtain a foreign identity result or use a forged GUC to lock a
foreign account; the older shared login retains its previous behavior.

## Staging rollout and rollback

Apply 0037 with the dedicated migrator during a reviewed lock window: adding a
policy to every forced-RLS table takes DDL locks and is not an online production
rollout claim. Create a unique login per fictional/staging tenant with no
`SUPERUSER`, `BYPASSRLS`, `CREATEROLE`, ownership or privileged membership; assign
one tenant through the provisioning helper. Keep its DSN private. Test the opt-in
API route and private workers with tenant-specific DSNs before routing any real
traffic. Never reuse one
scoped DSN across tenants. Review credential creation, rotation, pooling, identity
bootstrap and a two-tenant restore before considering hosted use.

To roll back an attempted scoped-login rollout, stop callers and revoke/disable
the affected login's ability to connect first. Restore service and schema only
under a reviewed backup/compatibility plan; do not drop the restrictive policies
or mapping while a scoped credential remains live. Existing shared logins are
unchanged but remain vulnerable to arbitrary-SQL tenant-GUC forgery; do not
interpret their synthetic CI as hosted containment.

## Evidence and remaining work

The synthetic PostgreSQL regression uses real non-superuser logins with two
fictional tenants. It proves own-tenant read/write, wrong-tenant read/write
denial under forged GUCs, identity-admin/session-role switch denial, stable
`session_user` under an allowed harmless role switch, mapping removal failure
closed, policy inventory coverage, two-tenant API search and wrong/missing/shared
route refusal. This does not prove an API SQL-injection path exists or is absent.
Worker routing, credential lifecycle, independent security review, operational
isolation and live rollout evidence remain open under issue #7.
