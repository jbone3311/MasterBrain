# ADR-230 — Restricted reviewed Email PDF replay command

Status: synthetic-only private command on an open PR. Unit/controller and
fictional command-to-PostgreSQL tests pass locally; actual immutable-image,
exact-head hosted and independent restore
gates remain. No live account or financial publication is authorized.

## Context

ADR-228 proves one retained MIME/PDF part can reproduce a complete text-layer
derivation through the pinned isolated worker. ADR-229 binds that proof to one
current reviewed attachment occurrence and appends a digest-only receipt. A
private operator still needs a narrow way to select the exact review without
turning the Brain API, an assistant or a source-effect command into the caller.

## Decision

Add `masterbrain email replay-tier-pdf --config PATH --review-id stier_... \
--tenant-bound-db [--check]`. The closed, private version-1 config requires one
account UUID, worker credential and token paths, an immutable `sha256:` PDF
image ID and absolute Docker binary. Optional encrypted retained-MIME storage
requires a paired private blob root and tenant-matching key file. The worker
token needs `brain.document.publish` and `email.evidence.read`; a shared or
owner database login is refused by the tenant-bound worker store.

Check mode authenticates and validates the exact active account, tenant login,
optional private storage configuration and current worker identity. It reads
no selected MIME/PDF, review row or receipt and does not construct a processor
or encrypted blob store. It reports configuration validity, never execution
verification. Execution constructs the pinned PDF processor only after these
checks, passes the exact account and review into ADR-229's worker store, and
reauthenticates inside the final receipt transaction and before return. Errors
are flattened so sensitive account, source and path details do not escape.

This command cannot move or rename an email or file, call Fastmail, approve a
fact, produce OCR, prove issuer authenticity or publish a financial claim.
Its receipt remains point-in-time; ADR-229's account/job transition race needs
a separate serialization fence before any live use. FOS-Master is unchanged.

## Verification and rollout

Unit tests cover check-mode non-read, exact config/account/worker scope,
immutable image validation, execution handoff, inactive account and unbound
login refusal, and CLI dispatch without DSN disclosure. A fictional end-to-end
command/database test verifies one receipt and refuses shared/owner logins.
Follow with actual immutable-image
container run, hosted exact-head gates and independent populated restore. The
explicit PDF-container suite now collects a fictional reviewed Email PDF
receipt through the actual built image; collection is not execution.
Check-only use does not assert execution readiness. Roll back by withholding
the private command and preserving any append-only receipts already written.
