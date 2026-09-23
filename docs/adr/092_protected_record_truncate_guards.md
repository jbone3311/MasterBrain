# ADR-092 — Refuse whole-table truncation of protected records

Status: accepted design; implementation and hosted verification pending.

## Context

[Issue #8](https://github.com/jbone3311/CW-EmailBrain/issues/8) identifies a gap in
the existing row-level `BEFORE UPDATE OR DELETE` protection. PostgreSQL `TRUNCATE`
does not fire row triggers or use tenant RLS. At the migration 0028 baseline, 56
tables have a direct `deny_evidence_mutation()` row trigger, yet a table owner with
`TRUNCATE` privilege can empty them without that guard. `recovery_jobs` and
`document_jobs` separately refuse row deletion, while `external_identities` audits
row deletion; truncation bypasses those protections too.

This is a privileged-database integrity risk, not evidence of a Brain API exploit.
The runtime role is non-owning, non-`BYPASSRLS`, and is not granted `TRUNCATE`.
Statement triggers do not defend against a malicious table owner who can disable or
drop them. Separation of duties, database audit, backups and restores remain required.

## Decision

Add forward-only migration 0030, after the verified migration-integrity 0029, with a
dedicated `BEFORE TRUNCATE FOR EACH STATEMENT` rejection trigger. Install it on every
current public table that has a direct `deny_evidence_mutation()` row trigger, plus
the two protected job tables and `external_identities`. The latter is mutable by the
administrator but cannot be silently wiped without its row-level identity audit.
The 0030 migration must not edit applied migration files or any retained row.

Discover the direct append-only tables from the PostgreSQL trigger catalog during
migration, under the already-required privileged migrator, and add the three named
special cases explicitly. Refuse an empty or incomplete discovery relative to the
accepted 0028 baseline. Future migrations that add protected tables must also add
the statement trigger and expand the catalog acceptance test. The target set and
trigger function are public-schema-only; no user-controlled identifiers are used.

Direct and foreign-key-cascaded `TRUNCATE` must both fail atomically. Ordinary
authorized row-level state transitions on the job and identity tables remain
unchanged; this decision adds no `DELETE` denial to `external_identities` and no
runtime grant, source effect, retention/purge implementation or FileOS cutover.

## Verification and rollout

Use disposable PostgreSQL 17 with synthetic rows. Prove the pre-0030 owner can
truncate a protected table (in a rolled-back disposable transaction), then apply
0030 and prove direct `TRUNCATE`, `TRUNCATE ... CASCADE`, and parent-cascade attempts
raise before loss. Catalog tests must compare the exact row-guarded table set to the
statement-guarded set, require the three named special cases, and inspect trigger
mode and function. Check unchanged data and row UPDATE/DELETE refusal, legitimate
job/identity row paths, runtime privilege denial, replay, full CI and populated
restore. No production database or real evidence is used in acceptance.

Rollout pauses writers, records a backup and a privileged inventory of enabled
triggers, applies 0030, verifies catalog and attempted truncation in staging, then
resumes. Rollback stops new code if needed but retains the additive guards; disabling
them is a separately reviewed administrative action, not an automatic down-migration.

## Alternatives rejected

- Relying on RLS or row triggers: neither covers `TRUNCATE`.
- Trigger-only claims of tamper-proof storage: owners can alter trigger definitions.
- Editing 0002–0028: applied checksums and provenance must remain intact.
- Blocking all administrator `DELETE` on identities: legitimate audited identity
  lifecycle is outside this issue and requires its own decision.
