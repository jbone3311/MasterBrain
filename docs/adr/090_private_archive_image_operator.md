# ADR-090 — Private one-member archive-image OCR operator

Status: checkpoint 5C accepted and implemented in `f658ace`;
[CI 35836198307](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35836198307)
and [restore 35836198414](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35836198414)
are green.

## Context

ADR-088 composes an exact current archive member with the isolated image OCR worker.
ADR-089 publishes one complete, nonempty result under a transaction-time parent/member
fence. Neither checkpoint gives an operator a command to invoke that chain. The
existing private archive-document command establishes the narrow one-member pattern.

## Decision

Add `masterbrain fileos archive-image` for one explicitly supplied inventory ID,
member locator and caller-owned UUID idempotency key. Extend the closed owner-private
archive configuration with a distinct, optional immutable `image_ocr_image_id`.
Require that field for this command while preserving existing text/document command
configurations. Keep the archive reader and image OCR processor in separate pinned,
restricted images.

Use the existing exact-scope worker identity (`brain.source.ingest` and
`brain.document.publish`), private-file validation and least-privileged database-role
preflight. `--check` validates arguments, configuration, root, identity and role; it
does not select a member, construct either worker, read source bytes or consume a key.

Execution resolves one current non-container member through forced RLS, reauthenticates
before the two-worker composition, accepts only a complete nonempty `extracted` OCR
result, reauthenticates before publication and again before returning. The existing
5B wrapper and transaction retain exact result validation, replay, current-parent and
sealed-member fences. Empty OCR, deferred, failed and unsupported results publish
nothing and the command reports one generic refusal. An uncertain response is retried
with the identical key and selection.

Return only the operation name, opaque inventory/source/item/version/evidence/document
identities, chunk count, changed/replay state and `source_effects: false`. Paths,
locators, image dimensions, OCR text, bytes, EXIF, credentials and raw faults never
enter command output. No scanner or source effect is authorized.

## Alternatives rejected

- Reuse `document_image_id`: OCR has a separate image, dependencies and contract.
- Add a Brain API route: this is a private one-shot worker operation.
- Select or enumerate images automatically: one explicit member keeps review and
  retry authority bounded.
- Publish blank OCR as a document: ADR-089 permits only nonempty complete text.
- Store image bytes or pixels: existing source-bound evidence and processor provenance
  are sufficient for this derivative.

## Acceptance and rollback

Prove closed configuration, immutable image IDs, exact scopes, private files,
non-consuming `--check`, repeated authentication, revocation, source/current-member
fencing, exact retry and conflict, output scrubbing, empty/unsupported/over-limit
refusal, two-worker faults, real chained containers, PostgreSQL RLS and populated
restore. Existing donor parity and source immutability gates must remain green.

Rollback removes the command and controller. Existing 5A composition, 5B append-only
receipts and retained evidence remain valid. This decision grants no preview, batch,
current-search activation, fan-out, scheduler, public mutation, source write or
FOS-Master cutover.

## Implementation

The accepted hosted run passed 2,652 PostgreSQL-backed Python tests, 134 browser
contracts and all restricted worker/container gates. Populated restore passed. No
live-source or production acceptance is implied.
