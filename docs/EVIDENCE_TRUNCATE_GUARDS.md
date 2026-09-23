# Protected-record truncation contract

ADR-092 addresses [issue #8](https://github.com/jbone3311/CW-EmailBrain/issues/8)
without claiming that triggers make privileged database administrators powerless.
Focused disposable-PostgreSQL verification, hosted CI and populated restore passed
on [PR #13](https://github.com/jbone3311/CW-EmailBrain/pull/13); independent review
and integration are pending.

## Scope

Migration 0030 must install a statement-level `BEFORE TRUNCATE` rejection trigger
on all 56 current public tables whose row-level `UPDATE OR DELETE` guard directly
calls `deny_evidence_mutation()`. It must also cover `recovery_jobs` and
`document_jobs`, whose specialized row guards refuse deletion, and
`external_identities`, whose row delete is audited. The latter three are not
append-only under every row operation; the new guard only prevents unlogged bulk
erasure. Current runtime roles have no `TRUNCATE` privilege and receive none.

New protected tables in later migrations must receive their own `TRUNCATE` guard.
This migration touches no existing evidence, job or identity rows and changes no
source/Email/FileOS effect. Approved retention and purge require a distinct,
reviewed administrative workflow with audit and restore strategy; this change does
not create one.

## Acceptance

- Catalog coverage is exact: each current direct row-guarded table and the three
  named special cases has an enabled, non-internal, public-schema `BEFORE TRUNCATE`
  statement trigger invoking the rejecting function.
- A privileged owner can reproduce the old gap in a disposable pre-0030 database;
  after migration, direct and FK-cascaded truncation fail with all synthetic rows
  and history intact.
- An ordinary runtime role lacks `TRUNCATE`; existing row-level mutation and
  legitimate job/identity transitions are unaffected.
- Replay, full PostgreSQL suite, deployment/docs gates, restricted workers and a
  populated logical restore pass before the PR is integrated.

The guard is defense against accidental or mistaken privileged SQL, not an
independent barrier against a hostile DBA. Forced RLS and ordinary grants protect
runtime use; backups, audit, separation of duties and operator review protect the
administrative boundary.
