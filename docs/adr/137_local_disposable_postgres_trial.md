# ADR-137: Disposable local PostgreSQL trial backend

Date: 2026-10-02. Status: accepted for synthetic testing only.

## Decision

The fictional cross-source trial may use either its existing disposable Docker
PostgreSQL 17 container or a newly initialized, per-run local PostgreSQL 17
cluster. Automatic selection prefers Docker when its command is available and
otherwise uses local PostgreSQL binaries. An explicit backend option makes the
choice testable. Neither path accepts a database URL, account, source root,
provider credential or existing PostgreSQL data directory.

The local path creates an unpredictable private temporary directory and its own
`initdb` cluster, a random database password, SCRAM host authentication and a
loopback-only listener on a free ephemeral port. It creates only a test-prefixed
database inside that cluster. It uses the same schema, least-privileged runtime
role, fictional seed and Brain API self-test as the Docker path. No globally
installed PostgreSQL service is started or stopped. On graceful exit, the
launcher stops only that exact cluster before removing its temporary files. If
stop cannot be confirmed, it preserves the cluster and prints the exact
temporary location for operator inspection rather than deleting possibly live
data. Secrets and source text are not printed.

This is a developer convenience, not a production database or hosted identity
boundary. PostgreSQL's data files are unencrypted temporary synthetic data;
the launcher never points at real data. A forced process kill can leave a
synthetic cluster behind, so the operator must inspect its exact path before
manual cleanup. FileOS and source-effect authority do not change.

## Validation and rollback

Test backend selection and refusal of missing/wrong-version binaries. Run the
actual local self-test on PostgreSQL 17 and retain the hosted Docker self-test.
The normal trial and all existing API isolation/citation tests remain the same.
Rollback removes the local backend and returns to the Docker-only launcher;
it does not alter schema, live sources or FOS-Master.
