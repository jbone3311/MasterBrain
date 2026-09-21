# ADR-032: bounded operator processing controller

Accepted for local/synthetic execution, 2026-09-20. No hosted or live-mail rollout.

## Decision

Expose existing approved recovery jobs through `email-brain process-jobs`. An
explicit private configuration fixes one account, an immutable local image ID,
Docker binary, worker credential registry/token paths and optional encrypted
object root/keyring. Runtime SQL credentials remain in `EMAIL_BRAIN_DSN`.
No identity, approval, service, provider connection or image is created implicitly.

Run one poll by default; bounded repeated polls are optional. SIGINT/SIGTERM stop
new claims and allow the current bounded processor to finish and clean up. A hard
kill relies on existing expiring SQL leases; it is not cancellation or cleanup proof.
Return fixed aggregate counters, never mail, paths, IDs, credentials or exceptions.
No-result does not prove an empty queue: work may be leased, delayed or inaccessible.

`--check` validates configuration, worker identity, current owner/account access
and optional private key material without claiming work or invoking Docker. It
explicitly does not certify image availability, processor isolation or hosted readiness.

Files must be bounded, owner-only regular files in private directories, opened
without following symlinks (including ancestors), outside Dropbox and the source
checkout. Reject duplicate JSON keys, unknown fields, path expansion and weak
permissions. Keys are confined to the authenticated tenant; no active write key is
selected. Files/configuration are operator authority, never email-supplied input.

Reauthenticate the fixed worker identity from private files on every poll and
before/after actual parsing. Expiry/removal/identity change stops the controller;
the token is never saved to SQL. File revocation is not atomic with SQL publication:
existing database membership/account locks and explicit cancellation remain the
strong transaction-bound revocation controls. Bootstrap auth is not production OIDC.

## Consequences and verification

API/parser gain no Docker access. Controller remains trusted and privileged; no
new SQL grants, schema, parser powers or binary document extraction. Tests cover
hostile configuration/files, scoped identity, bounded iteration, shutdown, scrubbed
errors, PostgreSQL ownership/restart/revocation and actual restricted-container CLI
execution. Existing queue tests remain authoritative for lease/crash fencing.

Rollback: stop controller invocation and disable new approvals; retain jobs,
evidence, keys and audit. Do not alter leases, reset consent or downgrade schema.
Production supervisor configuration, service principals, KMS and host acceptance
remain separate release gates.
