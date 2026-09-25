# ADR-105 — Least-privilege external identity administration

Status: accepted for synthetic implementation, 2026-09-25. This fixes
[issue #6](https://github.com/jbone3311/MasterBrain/issues/6); it does not
authorize a live identity provider, public enrollment API or production use.

## Problem and evidence

Migration 0013 forces row-level security on `external_identities` but grants only
a `SELECT` policy. An administrator without `SUPERUSER` or `BYPASSRLS` cannot
insert, update or delete a binding, even when explicitly granted table privileges.
On a disposable PostgreSQL 17 instance, a non-superuser role with table grants
received `new row violates row-level security policy` on a fictional insert.
Existing integration fixtures perform administrator writes as `postgres`, so they
did not exercise the intended enrollment role.

## Decision

Migration 0034 creates (or validates) a cluster-level, `NOLOGIN`, non-superuser,
non-`BYPASSRLS` role named `masterbrain_identity_admin`. It grants that role only
schema usage and `SELECT`, `INSERT`, `UPDATE`, `DELETE` on
`external_identities`, with a role-targeted forced-RLS policy. It does not grant
ownership, `TRUNCATE`, other tables, role creation or migration authority. A DBA
must separately grant membership to a named, audited administrator login after
reviewing existing role memberships; runtime and worker logins must not be members.
If the role already exists with members, migration refuses to extend those
members' authority to a new database. A DBA must review and temporarily revoke
membership before retrying, then grant it back only where intended.

The existing identity audit trigger runs as a tightly scoped `SECURITY DEFINER`
function because an administrator must not receive direct `audit_events` insert
permission merely to make the trigger work under forced RLS. Its body uses
schema-qualified tables, a fixed search path, no caller-controlled SQL, and
`session_user` as the database login in audit metadata. Public function execution
remains revoked. Existing binding immutability, scope/kind checks, revision
increments and append-only audit protections remain in force.

## Boundaries and verification

- The role can manage bindings across tenants by design, but cannot read other
  tenant tables or write audit rows directly. The admin login and membership are
  external operations, not inferred from an access token or request.
- Test the real non-superuser login for insert/update/delete, revision and audit;
  verify direct audit write and unrelated data access fail; verify the runtime
  login still cannot mutate bindings and cannot assume the admin role.
- Issue #7's caller-settable identity lookup context is separate. This decision
  does not claim that arbitrary SQL execution by a compromised runtime is safe.
- Apply 0034 forward-only with a privileged migrator, review group membership,
  then grant a dedicated login. Rollback is revoking that login's group membership
  and disabling the affected binding; preserve audit and migration history.
  Do not delete a role shared by another database or rewrite migration 0013.
