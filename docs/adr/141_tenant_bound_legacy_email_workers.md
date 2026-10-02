# ADR-141 — Tenant-bound database access for legacy Email workers

Status: accepted for synthetic/disposable implementation. This extends the
opt-in ADR-108/109 login fence through the three existing `email-brain` worker
commands. It is not hosted acceptance or closure of issue #7.

## Problem and decision

`sync-read`, `process-jobs` and `process-documents` each authenticate a
single-tenant private worker credential before constructing their SQL store,
but currently use the shared `EMAIL_BRAIN_DSN`. A stolen shared login can forge
the older tenant-context GUC; an application-level tenant check alone does not
contain arbitrary SQL. The read worker also reconstructs its store between
polls and must not silently return to a shared login.

Add explicit opt-in `--tenant-bound-db` to all three commands and matching
library controllers. After authenticating the exact existing worker identity,
construct every store, including the preflight and optional encrypted-object
store, with only that worker tenant mapped to `EMAIL_BRAIN_DSN`. The existing
`Store.connection` binding check must reject a shared, owner or wrong-tenant
login even under `--check`, before a provider request, Docker launch or job
claim. On each read-worker poll, reauthenticate and reconstruct the same bound
store. A config account ID, provider response, document or job may never select
the database tenant. Reuse the shared DataCore worker-store primitive rather
than adding another policy implementation.

Default local behavior, exact worker scopes, source/account checks, private
keyring behavior, failure scrubbing, recovery leases, provider-read opt-in and
PDF synthetic-only policy remain unchanged. This flag does not provision or
rotate a DBA-bound login and does not confer provider or source-write authority.

## Verification and rollback

Use two fictional tenants and real PostgreSQL non-owner logins. For each
controller, prove that own-tenant bound preflight succeeds while shared,
wrong-tenant and owner logins fail before side effects. Exercise a bounded
synthetic execution path for each worker type through the bound login, with
credential revocation, unchanged originals, and forged-GUC cross-tenant
read/write denial. Cover CLI flag forwarding, default compatibility, invalid
flag types, optional encrypted-object store construction and read-worker
reopen. Run full PostgreSQL, browser, deployment, runtime and restore gates.

Rollback stops the opt-in workers and disables/revokes the scoped login under
DBA control, preserving SQL policies, evidence, jobs and checkpoints. A hosted
operator must not fall back to the shared login to clear a failure. Hosted
credential lifecycle, private library caller routing outside these commands,
adversarial review, operational restore and live-source acceptance remain
separate issue #7 gates. FOS-Master is unchanged.
