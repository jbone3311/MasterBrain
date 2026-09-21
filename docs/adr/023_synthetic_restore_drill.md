# ADR-023 — Real synthetic PostgreSQL restore drill

Accepted for disposable CI only, 2026-09-20. No production backup or restore
authorization is implied.

Create a fresh PostgreSQL 17 Docker container with an unguessable ownership label,
loopback-only random port and no host volume mounts. Inside that isolated cluster,
create newly named `email_brain_test_restore_*` source and target databases.
The script accepts no existing database DSN, archive input or destination override.
It seeds only synthetic fixtures through the current application, takes a custom
format `pg_dump`, restores it with PostgreSQL 17 `pg_restore` into the empty target,
recreates least-privilege runtime grants, then validates content and authorization.

The archive exists only in a private temporary directory, with mode 0600, and is
never printed, committed or uploaded as an artifact. Only counts, digest equality,
elapsed time and pass/fail are reported. Docker utility errors are scrubbed. Remove
only the exact container created by this invocation after checking its ownership
label; no broad Docker prune, existing database drops or remote Docker access.

Custom-format archives preserve database schema/data, but global roles are not
included. The drill intentionally provisions a fresh restricted runtime role and
reapplies reviewed grants. It must demonstrate forced RLS, foreign-tenant denial,
immutable evidence protections, cursor/proposal/attachment/quarantine preservation
and unchanged byte hashes after restoration.
The synthetic seed also includes human-reviewed rule proposals, simulation
receipts and activated revisions; restoration must preserve tenant-specific virtual
classifications while preventing foreign receipt use and leaving evidence unchanged.

This proves a synthetic logical restore on the current PostgreSQL major version,
not encrypted backup storage, cloud keys, object-store coordination, PITR, real
mail volume, production RPO/RTO or disaster recovery. A later production restore
requires isolated infrastructure, backup/key access and explicit operator approval.

Sources: [PostgreSQL 17 pg_dump](https://www.postgresql.org/docs/17/app-pgdump.html),
[PostgreSQL 17 pg_restore](https://www.postgresql.org/docs/17/app-pgrestore.html).
