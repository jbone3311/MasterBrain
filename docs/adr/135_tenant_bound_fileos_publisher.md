# ADR-135 — Tenant-bound database login for the private FileOS publisher

Status: accepted for synthetic/disposable implementation. This is one private
worker tranche of issue #7, not hosted multi-tenant acceptance.

## Problem

The API has an opt-in tenant-routed login fence (ADR-109), but `masterbrain
fileos publish` still creates a shared-DSN `Store`. Its application context
checks tenant and worker scope, yet someone holding that database credential
with arbitrary SQL can forge the old tenant GUC. A FileOS worker is a useful
first migration target because it authenticates one exact private worker
credential before any database transaction, and its command already has
non-consuming check mode and no source effect.

## Decision

- Add an explicit `--tenant-bound-db` private operator option. After exact
  worker authentication, the command binds the supplied `MASTERBRAIN_DSN` to
  that worker identity's tenant in `Store`. Every transaction then uses the
  existing ADR-108/109 per-connection `session_user` binding check. A shared,
  unbound, owner, or wrong-tenant login fails before publication, including
  check mode. Request content, manifest, source text and model output cannot
  choose the tenant login or switch this option.
- The DSN still comes only from `MASTERBRAIN_DSN`, not a command argument or
  source file. The worker process receives only its one tenant login; it does
  not load the API's multi-tenant route file or a table-blind lookup login.
  Application scope, source/root/manifest checks and transaction-time owner
  checks remain unchanged. The bound login is tenant-scoped, not source-scoped.
- Preserve the legacy command form for local compatibility. It remains
  unsuitable for a hosted arbitrary-SQL/credential-theft threat model. Other
  Email/FileOS private controllers are not silently routed by this ADR.

## Verification and rollback

Use two fictional tenants and real non-owner PostgreSQL logins. Prove check,
publish and replay with the correct bound login; reject a shared/unbound login,
a login bound to the other tenant, and a revoked local worker before intake.
Prove a stolen bound DSN cannot read/write the other tenant after forged GUCs.
Keep output and failures content-free; run the full PostgreSQL, browser, strict
runtime, deployment, restore and documentation gates. No FOS-Master code or
source file may change.

Rollback is to stop the tenant-bound worker and revoke/rotate its login under
DBA control. Keep the restrictive database policies and committed evidence;
do not fall back to a shared login for hosted work. This does not close issue
#7 until every private worker and operational credential/restore path is
reviewed and tested.
