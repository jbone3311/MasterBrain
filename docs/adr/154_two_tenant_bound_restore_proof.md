# ADR-154 — Exercise tenant-bound logins across a synthetic restore

Status: accepted for the disposable PostgreSQL 17 drill only. This is not
hosted multi-tenant or credential-lifecycle acceptance.

## Context

The restore drill already compares two fictional tenants' evidence, identity
bindings, encrypted objects, RLS and current search after a logical restore.
Its runtime checks use one shared database login, however. Issue #7 requires
evidence that the opt-in `session_user` tenant fence survives a restored
database and a new set of tenant-scoped credentials.

## Decision

- Before the dump, provision one non-owner, non-BYPASSRLS login for each
  fictional tenant through the existing DBA-only `grant_tenant_runtime` helper.
  Verify each can search its own evidence and not the other's.
- After restoring the database and separately backed-up encrypted objects,
  create two *new* target logins and bind them to the same two tenant IDs.
  Verify the restored binding rows, own-source reads, foreign-source absence,
  and direct arbitrary-SQL attempts to forge tenant/actor GUCs, read foreign
  tenant/evidence rows, write foreign audit rows or assume identity-admin role.
- Keep the current shared-login restore tests as a compatibility check. The
  additional bound-login proof cannot turn shared login mode into a hosted
  security claim. Output contains counts and fixed stage/status codes only;
  passwords, DSNs, evidence and SQL errors remain suppressed.

## Limits, verification and rollback

The source and target databases live in one **disposable Docker cluster**;
cluster-global role objects are not themselves backed up or restored. The
target logins are newly created after `pg_restore --no-acl`. This does not
exercise real credential escrow, rotation, pool draining, active-session
termination, a separate-cluster disaster recovery or an adversarial hosted
operator. Those remain issue #7 gates. The temporary cluster and archive are
removed by the existing ownership-checked cleanup. Failure does not alter a
real database, FOS-Master, or product runtime behavior. Run offline safety
tests, the actual PostgreSQL 17 restore job, full CI and strict runtime.
