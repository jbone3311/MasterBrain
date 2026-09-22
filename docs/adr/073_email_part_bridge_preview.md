# ADR-073 — Current Email attachment and document bridge preview

Status: implemented; hosted verification pending.

## Context

ADR-071 and ADR-072 provide reviewed selection and fail-stop execution for current
message versions. Attachments and approved document derivatives already have safe
one-item bridges, but their prerequisites differ: an attachment requires a current,
visible, bridged parent message; a document requires that same chain plus an existing
attachment bridge and a completed approval tied to the immutable extraction.
Guessing either queue in an executor would recreate discovery and retry hazards that
the sealed message batch deliberately removed.

## Decision

Add a private, read-only `masterbrain email bridge-parts-plan` operator for one
explicit account and one explicit `attachment` or `document` kind. Each kind has its
own stable `(created_at, UUID)` order and opaque UUID cursor; queues are never merged.
The limit is 1–100 and defaults to 25.

An attachment result contains only its legacy attachment UUID, legacy parent-version
UUID, receipt time, intake outcome and `already_bridged`. It is eligible only when the
legacy message is visible and current, the exact parent version has a DataCore bridge
receipt, and that shared parent item still points at the bridged version.

A document result contains only its legacy extraction UUID, legacy attachment UUID,
legacy parent-version UUID, extraction time, extraction status and
`already_bridged`. It is eligible only when the attachment meets the current-parent
rules above, already has a current shared attachment bridge, and the immutable
extraction is `extracted` or `partial` with a matching completed `result_saved`
approval job. If several completed jobs reference the same extraction, the preview
returns the extraction once.

The response declares the account, kind, results, next cursor, bound, and
`source_effects: false` / `data_effects: false`. It contains no subject, address,
filename, part path, media content, extracted text, provider identifier, shared
locator or implicit idempotency key. `--check` authenticates, validates the closed
private configuration and exact bridge scopes, and checks the safe database role
without reading the account or either queue.

## Consistency and failure rules

Each page is one tenant-scoped database transaction. A cursor must belong to the
selected account and kind, but the cursor row need not remain eligible; this keeps
continuation stable when a prior row becomes bridged or its parent becomes stale.
The preview is an observation, not a snapshot or execution authority. Operators must
review a page and later seal exact IDs and keys in a separate, digest-bound plan.

Unknown accounts/cursors, invalid kinds/bounds and authorization changes fail closed.
No preview follows another page, reserves work, creates receipts, approves a document,
reads bytes, contacts a provider, or changes a mailbox.

## Acceptance and rollback

Unit and CLI tests must prove exact scopes, non-consuming check mode, closed output and
exact dispatch. PostgreSQL must prove stable pagination, dependency filtering,
already-bridged labels, duplicate-approval collapse, message update/delete/quarantine
transitions, tenant isolation and no data writes. Hosted CI and populated restore must
remain green. Rollback removes only the preview method and command; existing one-item
bridges and message batch behavior remain unchanged.
