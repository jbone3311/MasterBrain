# ADR-237 — Tenant-bound command for one reviewed FileOS XLSX replay

Status: synthetic command-to-database path implemented on an open PR.

## Decision

Expose ADR-236 only through `masterbrain fileos replay-tier-xlsx-tables` with
an exact `stier_...` review ID and a closed, private version-1 config. The
config binds one FileOS source ID and absolute physical root, one immutable
`sha256:` document image ID, an absolute Docker binary, and private worker
credential/token files. The worker token has exactly
`brain.document.publish`; the database login must be DBA-enrolled for that
same tenant. The DSN is supplied through `MASTERBRAIN_DSN`, never the config.

Check mode authenticates the worker, verifies the tenant-bound login and root
identity, and checks config/image syntax. It neither reads the selected XLSX
nor review row, constructs a processor, contacts Docker, or writes a receipt.
It does not certify that execution will succeed. Execution constructs the
restricted pinned-image table processor, checks the exact current reviewed
source and source grant, replays its bytes, reauthenticates inside the final
transaction, and seals only the digest/count receipt. It reauthenticates once
more before returning a content-free result. Errors are fixed and scrubbed.

## Acceptance and limits

Fictional tests cover closed/private config, exact worker scope, no-selected-
source-read check mode, shared/owner login refusal, source/review binding,
command-to-PostgreSQL receipt, unchanged bytes and scrubbed output. The
actual-image reviewed receipt case is collected in the explicit document
container suite but has not run locally. Hosted exact-head CI and independent
restore are still required. There is no unattended scan, table/cell API,
source file effect, live-root permission, financial approval or FOS-Master
cutover.
