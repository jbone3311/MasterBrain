# ADR-109 — Tenant-routed database access for the Brain API

Status: accepted for a synthetic, opt-in service path. Issue #7 remains open.

## Decision

The service may use a private, versioned routing file containing one identity-only
PostgreSQL DSN and one distinct tenant-bound login DSN per configured tenant. Token
verification precedes exact identity resolution on the identity-only connection.
The resulting tenant ID selects a configured data DSN; no request field, caller GUC,
or token text directly selects a database credential. Every data connection checks
that its immutable `session_user` is a member of the tenant-runtime marker and that
the database's 0037 fence accepts the selected tenant. A missing or mismatched route
fails closed before tenant SQL. A login without a binding is never a fallback.

The identity-only login has no public-table privileges or role memberships. The
DBA explicitly grants it only the exact identity resolver; ordinary PUBLIC
function/catalog privileges still apply and must be audited. Existing
single-DSN operation stays for
local compatibility, but cannot be described as hosted multi-tenant containment.
The private file is read with the existing bounded, no-follow, owner-only reader;
it never enters Git, logs, API responses, or command output.

## Alternatives and limits

One global runtime DSN plus caller-settable tenant GUCs is insufficient under an
arbitrary-SQL or stolen-credential threat. One explicitly configured login per
tenant is acceptable for this bounded opt-in path; pooling and unbounded tenant
creation are not implemented. The identity resolver still exposes an exact
binding to anyone possessing a valid lookup tuple and the lookup credential. It
does not expose a table scan, but key enumeration and credential compromise remain
operational threats.

This change covers the `serve` API process. Existing private Email/FileOS worker
commands still use their explicit DSNs and are **not** automatically tenant-routed.
Credential creation, rotation, pool draining, revocation, two-tenant restore,
hosted adversarial review, and live rollout remain release gates. No provider,
FileOS donor, mailbox-write, or source-effect authority changes.

## Verification and rollback

Synthetic PostgreSQL tests must use real distinct non-owner logins, prove two
tenants can authenticate and search only their own evidence, reject wrong/missing
routes and shared/unbound DSNs, and exercise forged GUCs on a stolen tenant DSN.
Configuration tests reject symlinks, broad file permissions, duplicate tenant
keys, reused database users, and malformed DSNs without printing secrets.

Rollback stops the opt-in service and returns to the prior *local-only* deployment
configuration; it does not remove migration 0037, weaken RLS, or permit a hosted
shared-credential deployment. Rotate/revoke any compromised login under the DBA's
reviewed credential procedure. The FOS-Master donor remains unchanged.
