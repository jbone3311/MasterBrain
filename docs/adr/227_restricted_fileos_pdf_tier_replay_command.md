# ADR-227 — Tenant-bound operator command for one FileOS PDF tier replay

Status: implemented and executed only with fictional PDF data and a simulated
restricted document pipe on an open PR. Hosted exact-head, actual immutable-
image container and independent restore gates remain open. No live root,
financial publication or FileOS cutover is authorized.

## Context

ADR-226 added an internal, review-bound FileOS PDF text-layer replay receipt.
Operators need a narrowly authenticated way to execute exactly one selected
review without exposing database, filesystem or Docker authority to Brain API
clients. The existing FileOS tier-text operator pattern supplies a no-source-
read check and tenant-bound login fence.

## Decision

`masterbrain fileos replay-tier-pdf --config ... --review-id stier_... \
--tenant-bound-db --check` accepts a closed version-1 private JSON config with
one source ID, absolute physical root, immutable `sha256:` document image ID,
absolute Docker binary, and private 0600 credentials/token paths under a 0700
directory. The expiring worker token has **exactly**
`brain.document.publish`; the database login must be DBA-enrolled for that
worker's tenant. The DSN is supplied only through `MASTERBRAIN_DSN`.

Check mode validates config shape, worker, bound login and physical root
identity. It neither selects the review nor opens its PDF, constructs the
document processor, contacts Docker or writes a receipt. It validates only
the image/binary *shape*, not image availability or its runtime isolation;
`configuration_valid` is not `execution_verified`.

Execution constructs the exact-image restricted processor and calls the
ADR-226 worker operation for one review/source. That operation binds and
rechecks current source, evidence, normalized document, grants, exclusion and
PDF derivation under a final locked transaction. The command reauthenticates
inside that transaction and after execution. Revocation aborts the receipt.
Errors are fixed and scrubbed; output omits paths, source content, credentials
and Docker diagnostics. There is no automatic scan, scheduled job, source
file effect, public API write or financial approval. FOS-Master is unchanged.

## Acceptance and next gate

Fictional tests must prove closed/private config, exact worker scope, no
selected-source read or processor construction in check mode, shared/owner
DSN refusal, exact source/review binding, actual command-to-database receipt,
unchanged bytes and final authorization rollback. Run full local, hosted and
independent restore gates before merge. Next validate the actual immutable
container image, then address OCR/visual completeness, Email attachment PDF
derivation and issuer/conflict policy before any financial claim. A live root
requires a new owner authorization.
