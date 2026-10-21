# ADR-219 — Tenant-bound operator command for one FileOS tier-text replay

Status: implemented and exercised only with fictional local sources on an
open PR; hosted exact-head, independent restore and live-source authorization
remain open.

## Context

ADR-218 introduced a point-in-time FileOS byte-to-text replay for a human
source-tier review, but only internal callers could invoke it. An operator
needs a narrow way to run exactly one selected review, with a preflight that
does not read the selected file or write a receipt. The older FileOS command
framework already has private configuration, worker tokens and tenant-bound
database login checks.

## Decision

`masterbrain fileos replay-tier-text --config ... --review-id stier_... \
--tenant-bound-db --check` authenticates a **document-publish-only** worker
from a 0600 token/credential pair in a 0700 directory, checks the closed
versioned config, verifies the database login is bound to the worker's exact
tenant and verifies the physical root identity. Check mode does not select a
review, read a source file or write any record. Execution (without `--check`)
requires the same tenant-bound login, exact review ID and config source ID.
It reauthenticates before execution and again inside the final locked
transaction before the immutable replay receipt is inserted. If the token is
revoked then, the transaction rolls back. All failures emit a fixed scrubbed
error; credentials, paths and source content are never returned.

The command can read one configured source file and write one database
receipt, but cannot move, rename, delete or modify source files. The receipt
still represents a point-in-time text replay only. No PDF/OCR/spreadsheet
coverage, Email-byte equivalent, current-on-disk certificate, issuer
authenticity or financial-claim approval is inferred. There is no automatic
scan, scheduled run, public API write, or FileOS cutover. FOS-Master is
unchanged. This command has only been **executed against fictional local
data**; using any live root requires separate owner authorization and gates.

## Acceptance and next gate

Tests must prove closed config and exact worker scope, no side effects in
check mode, tenant-bound DSN enforcement including shared/owner refusal,
source-ID binding, actual synthetic command execution, no file mutation,
idempotent point-in-time receipt, and revocation rollback inside the final
transaction. Full local and hosted suites plus independent restore remain
required. Next: PDF/OCR and spreadsheet coverage proofs, Email-byte replay,
issuer/conflict policy, and only then an evidence-linked financial publication
gate. A live pilot is not authorized by this ADR.
