# ADR-138 — Tenant-bound database login for private FileOS indexing

Status: accepted for synthetic/disposable implementation. This extends ADR-135's
opt-in worker-login fence; it does not close issue #7 or authorize hosted use.

## Problem

The private `masterbrain fileos index` operator builds and activates a generation
for one completed FileOS run, or reactivates an older generation for rollback.
Its exact worker scopes and application tenant context do not contain a stolen
shared PostgreSQL credential: arbitrary SQL on that credential can forge the
older tenant GUC. The publisher has an opt-in bound-login path, but the index
operator still uses the shared `Store` path.

## Decision

- Add `--tenant-bound-db` to both build-and-activate and activation-only modes.
  Authenticate the existing private worker credential first, then bind the
  runtime `MASTERBRAIN_DSN` to that worker's one tenant in `Store`. The
  per-connection ADR-108/109 login check rejects shared, owner and wrong-tenant
  logins before check mode reports success or a generation is changed.
- Preserve the existing exact scopes, source/run/generation selection,
  idempotency, reauthentication points and content-free output. The DSN remains
  runtime-only, not a request/config value. No source file is opened or changed
  by the index operator, and v2 generation activation remains forbidden in SQL.
- Keep the legacy mode for local compatibility, explicitly not for a hosted
  arbitrary-SQL/credential-theft threat model. Do not silently route other
  private workers or treat a tenant login as a source-level grant.

## Verification and rollback

On two fictional tenants with real non-owner PostgreSQL logins, prove correct
bound-login check, build, replay, second generation and activation-only rollback;
reject shared, wrong-tenant and owner logins in both modes. Prove forged GUCs on
the bound login cannot read/write the other tenant. Preserve worker revocation,
exact-scope and no-source-effect tests. Run PostgreSQL, full unit, browser,
deployment, restore and documentation gates.

To roll back this option, stop the worker and revoke/rotate its login under DBA
control. Keep restrictive RLS and immutable generation/activation history. Never
fall back to the shared login for hosted operation. Remaining private workers,
credential lifecycle, hosted adversarial testing and FileOS donor cutover remain
separate gates.
