# ADR-106 — Exact identity resolution without caller-settable lookup context

Status: accepted for synthetic implementation, 2026-09-25. This is a bounded
hardening tranche for [issue #7](https://github.com/jbone3311/MasterBrain/issues/7),
not closure of that issue or authorization for hosted access.

## Problem

Migration 0013 let the runtime read `external_identities` through a forced-RLS
policy keyed entirely by custom transaction settings. Any SQL execution under the
runtime credential could set those values and query the table without an actually
verified token. A tenant is not known before identity resolution, so adding a
tenant predicate to that lookup would not solve the bootstrapping problem.

## Decision

Migration 0035 replaces the lookup policy with an exact-key, active-only,
`SECURITY DEFINER` resolver. The resolver returns only binding ID, tenant, actor,
scopes, kind and revision; it never returns the external subject or issuer. It has
a fixed search path, schema-qualified table, no dynamic SQL and no mutation. Public
execution is revoked; `grant-runtime` grants execute to the selected non-owner
runtime role and revokes its direct identity-table SELECT. Grant refresh and runtime
connection preflight both refuse identity-table SELECT inherited through another
role, including an accidental administrator membership. The application calls it
only after verifying the access token and again for every authorized transaction.
The separate administrator policy from ADR-105 is unchanged.

Historical pre-0035 schemas remain supported by `grant-runtime` for upgrade tests;
production must apply 0035 and refresh grants before starting the new runtime.
An old runtime binary that still queries the table will fail closed after 0035.

## Residual threat and verification

The resolver accepts tuple arguments from its caller. A compromised runtime
credential can still probe guessed tuples and, more importantly, set the other
tenant-context GUCs that protect evidence tables. This tranche prevents direct
identity-table enumeration; it does **not** prove containment of arbitrary SQL,
SQL injection, or a stolen runtime DSN. Issue #7 remains open for a separate
credential/tenant-isolation design and adversarial test before hosted release.

Regression must show correct and wrong-tuple resolution, no direct runtime SELECT
even after forged GUCs, unchanged revocation/revision checks, administrator writes
and populated upgrade/restore. Rollback stops the API and restores the previous
binary and schema from a reviewed backup; do not re-add the GUC policy casually or
rewrite migration history.
