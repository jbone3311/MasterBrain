# ADR-155 — Rehearse two-tenant restore into a fresh PostgreSQL cluster

Status: accepted for the disposable synthetic drill only. This supersedes
ADR-154's same-cluster limitation, not its hosted-acceptance warning.

## Context

ADR-154 verifies the DBA-bound tenant-login fence before and after a logical
restore, but its source and target databases share a Docker PostgreSQL cluster.
Database roles are cluster-global, so that test does not prove recovery when
none of the source role objects exist in the target. It also leaves restored
role-name bindings for source logins alongside newly provisioned target logins.

## Decision

- Run two independently labelled, loopback-only, disposable PostgreSQL 17
  containers with distinct generated passwords and databases. Dump only from
  the source container and restore only into the empty target. Verify both
  server/utility versions and that the container identities differ. Before
  `pg_restore`, explicitly create only the two fixed no-login marker roles
  referenced by dumped policies; refuse a preexisting role of either name.
- Preserve the existing byte-for-byte database and encrypted-object comparison
  before any target-side identity administration. Verify source runtime roles
  do not exist in the target cluster. Then remove their now-unusable restored
  role-name bindings through the DBA path, retaining the audit tombstones,
  before provisioning two fresh target logins bound to the same tenant IDs.
- Run the ADR-154 own/foreign evidence, forged-GUC, denied foreign write and
  denied role-switch checks with actual target logins. Require no stale source
  binding remains. Cleanup examines each exact container name, label and ID;
  failure to clean one must not skip an attempt to clean the other.

## Verification, limits and rollback

Offline tests cover both container ownership/cleanup paths and unsafe names.
The required CI restore job performs the actual cross-container PostgreSQL 17
dump, restore, role re-enrollment and authorization checks. Full CI, strict
runtime and documentation gates remain required. Output exposes only fixed
stages, counts and pass/fail states, never passwords, DSNs or content.

Global role objects and credentials are not included in `pg_dump`; this
bootstrap restores only policy dependencies, not tenant login secrets or
identity-admin memberships/grants. This is still a fictional, ephemeral
recovery rehearsal. It does not prove
credential escrow, rotation, active-session termination, pool draining,
managed-cloud restore, RPO/RTO or hosted adversarial acceptance. Shared-login
mode remains unsuitable for a hosted multi-tenant claim; issue #7 stays open.
No production database, source account, FOS-Master checkout or FileOS current
state changes. Rollback is to revert the drill implementation after preserving
its CI receipt, not to weaken runtime isolation.

PostgreSQL documents that [`pg_dump` excludes cluster-global roles](https://www.postgresql.org/docs/17/app-pg-dumpall.html)
and [`pg_restore --no-acl` omits grants](https://www.postgresql.org/docs/17/app-pgrestore.html).
