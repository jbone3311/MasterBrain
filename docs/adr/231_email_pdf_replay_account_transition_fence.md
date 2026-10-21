# ADR-231 — Serialize reviewed Email PDF replay with account transitions

Status: synthetic-only worker and additive database function on an open PR.
Fictional PostgreSQL race, tenant-login, migration and recovery tests pass
locally. Hosted, actual-image and independent restore gates remain.

## Context

ADR-229 rechecks an active account before appending a reviewed Email PDF
text-layer receipt, but the worker could not lock `mail_accounts`: granting it
table UPDATE authority merely for `SELECT ... FOR SHARE` would expand its
privileges. The authorized Fastmail enroll/disconnect path uses a transaction-
scoped advisory lock for the tenant/account pair. A direct privileged status
update need not take that lock. An approved `document_jobs` row is terminal
and immutable once completed, so it has no ordinary completed-to-other-state
transition to serialize; this does not defend against a malicious database
owner disabling protections.

## Decision

In the final receipt transaction, acquire the same tenant/account advisory
lock used by the controlled account transition, then call a narrow `SECURITY
DEFINER` function that locks the exact `mail_accounts` row `FOR SHARE` and
returns whether it is still active. The function requires the authenticated
session login to be bound to that tenant, matching the transaction tenant
context and an enrolled actor. It has a fixed `pg_catalog` search path and
accepts only tenant/account UUIDs. Runtime roles receive no account UPDATE,
DELETE or cross-tenant authority. Migration 0080 grants the function directly
to existing bound logins; future `grant_tenant_runtime` enrollments receive it
only after the safety checks. Shared runtime and database-owner logins are not
the worker path. The worker then repeats its full reviewed source, job,
exclusion, grant and authorization basis check before insert.

The order matters: advisory lock first, account row lock second. Controlled
disconnects take advisory lock before updating the row; direct privileged
updates that omit it block on the row lock. This avoids a lock-order cycle
between the controlled transition and the receipt insert's account foreign
key. A receipt is valid at its transaction point, not a promise that the
account remains active forever. It still proves only a PDF text layer, not
OCR, sender/issuer authenticity, financial truth or live Fastmail readiness.

## Verification and rollback

Fictional PostgreSQL races prove both orderings: a controlled disconnect
winning the advisory lock makes replay refuse with no receipt; replay winning
both locks commits a digest-only receipt while a direct privileged status
update waits, then the update completes. The function refuses wrong tenants
and nonexistent accounts, and a shared runtime login lacks EXECUTE. Existing
receipt, private-command, migration integrity and populated-recovery suites
must pass. Roll back by stopping the private worker and migrating forward;
do not delete append-only receipts or relax database grants. Live mail remains
closed until separate real-image, hosted, restore and provider acceptance.
