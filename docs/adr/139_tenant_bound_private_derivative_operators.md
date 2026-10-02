# ADR-139 — Tenant-bound database access for private derivative operators

Status: accepted for synthetic/disposable implementation. This extends the
opt-in login fence of ADR-135 and ADR-138, not hosted acceptance or issue #7
closure.

## Problem

The private Email bridge and FileOS archive derivative commands authenticate
one exact worker before opening PostgreSQL, but currently construct a shared-DSN
`Store`. Their application tenant context does not contain a stolen shared
credential with arbitrary SQL: that credential can forge the older tenant GUC.
The commands include single-target, read-only preview and sealed-batch modes;
all can disclose or change tenant data, so partial command coverage would leave
an avoidable alternate path.

## Decision

- Add opt-in `--tenant-bound-db` to every private `masterbrain email bridge*`
  and `masterbrain fileos archive-*` command, including previews and batches.
  Authenticate the existing worker credential first, then construct a `Store`
  with only that worker tenant mapped to the runtime `MASTERBRAIN_DSN`. The
  ADR-108/109 per-connection check must refuse an unbound, owner or
  wrong-tenant login before `--check` succeeds or any target is read.
- Put the common store-construction rule in a small DataCore database helper.
  Keep each command's existing exact scopes, source/target validation,
  reauthentication, idempotency, extraction containment, safe output and
  failure scrubbing. A batch must use the same bound store for every item;
  no item or plan may choose a database route.
- Preserve explicit legacy local mode for compatibility, without claiming it
  is suitable for a hosted arbitrary-SQL/credential-theft threat model. The
  DSN remains runtime-only, not in source material or private plans. A
  tenant-bound login is not a source-level grant.

## Verification and rollback

Use real non-owner logins for two fictional tenants. Test each command's
non-consuming preflight with own, shared, wrong and owner logins; exercise
representative Email bridge and archive preview/publication through the bound
login, including replay and revoked-worker refusal. Confirm a forged tenant
GUC cannot read or write the other tenant. Run the full PostgreSQL, browser,
deployment, strict-runtime, restore and documentation gates. FOS-Master and
source files remain unchanged.

Rollback means stop affected workers and revoke/rotate the scoped login under
DBA control. Retain database policies, receipts and evidence; do not fall back
to the shared login for hosted work. Legacy Email workers, other private
controllers, credential lifecycle and hosted adversarial/restore evidence
remain separate gates under issue #7.
