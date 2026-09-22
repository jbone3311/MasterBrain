# ADR-072 — Sealed explicit Email bridge batch

Status: implemented; hosted verification pending.

## Context

ADR-071 can safely preview current bridge candidates, but a preview is intentionally
mutable observation rather than execution authority. An executor must not silently
continue pagination, rediscover a mailbox, invent retry keys or change its target set
after operator review.

## Decision

Introduce an owner-private batch-plan file and later a
`masterbrain email bridge-batch` operator. The closed plan contains:

- `version: 1`, one explicit account UUID and the exact bridge `code_revision`;
- 1–100 ordered items, each with one legacy version UUID and one UUID idempotency key;
- a canonical SHA-256 over version, account, code revision and ordered items.

Version IDs and idempotency keys must each be unique. The plan digest must match its
canonical payload and its code revision must match the closed bridge configuration.
The command never follows a preview cursor or adds candidates. `--check` authenticates,
validates private files, bounds, identities and digest, confirms the safe runtime role,
and performs no target lookup or write.

Normal execution reauthenticates before every item and calls the existing one-item
bridge transaction with the plan's exact version/key pair. That transaction remains
the authority for account membership, visibility, current-version fencing,
idempotency and provenance. Execution is fail-stop in listed order: the first refusal
or unavailable identity stops later items. A retry uses the unchanged file and digest;
completed items replay idempotently and execution resumes from the first unrecorded
item without treating failures as success.

The content-free receipt includes plan SHA-256, requested/completed/replayed counts,
ordered per-item version UUID plus `recorded` state, `complete`, and the failed version
UUID/error code when stopped. It includes no Email content, provider identity or shared
locator. No database batch table is introduced initially because existing immutable
per-item receipts are the recovery authority; a durable batch receipt requires a later
ADR if operational evidence shows it is needed.

## Safety and compatibility

The plan file must be regular, owner-private and bounded. The executor contacts no
provider and changes no mailbox. It cannot bridge attachments/documents, discover new
messages, skip a failed item, run concurrently within one invocation or perform
best-effort continuation. Existing one-item commands remain supported and unchanged.

## Acceptance and rollback

Tests must prove canonical digest validation, private-file enforcement, all duplicate/
bound/config failures, non-consuming check, exact ordered dispatch, fail-stop behavior,
revocation between items, unchanged-plan retry/replay, stale/hidden-version refusal,
tenant isolation and content-free receipts. PostgreSQL must demonstrate an injected
mid-batch failure followed by safe exact-plan retry. Hosted CI and restore must remain
green. Rollback removes only the plan schema and batch operator.
