# ADR-074 — Sealed Email attachment and document bridge batches

Status: accepted; hosted PostgreSQL and restore verification green.

## Context

ADR-073 provides separate, reviewed pages for current attachment occurrences and
approved document derivatives. Those pages are mutable observations, not execution
authority. Multi-item execution must not combine dependency levels, discover another
page, invent retry identities or continue after a prerequisite changes.

## Decision

Add an owner-private, closed plan and later a
`masterbrain email bridge-parts-batch` command. The plan contains:

- `version: 1`, one explicit account UUID, one exact `kind` (`attachment` or
  `document`) and the bridge configuration's exact `code_revision`;
- 1–100 ordered items, each with one opaque `legacy_id` and one UUID idempotency key;
- `plan_sha256`, the canonical SHA-256 over version, account, kind, revision and the
  ordered items.

Legacy IDs and idempotency keys must each be unique. Including the kind in the digest
makes mixed attachment/document plans impossible. A plan never contains filenames,
part paths, content, provider identities, preview cursors or shared locators.

`--check` validates both owner-private files, the closed schema, digest, bounds,
revision, exact worker scopes and safe runtime role without looking up the account or
targets. Normal execution reauthenticates before each item and dispatches the exact
ID/key pair to the existing one-item attachment or document transaction. A batch-only
account fence must reject a target outside the sealed account without changing the
legacy one-item idempotency and replay ordering.

Execution is serial and fail-stop. The first conflict, missing identity or validation
refusal stops all later items. Retrying the byte-for-byte unchanged plan replays prior
immutable receipts and continues with the original keys. There is no skip, automatic
retry, best-effort mode, implicit pagination or cross-kind chaining.

The content-free receipt contains operation, kind, plan digest, requested/completed/
recorded/replayed counts, ordered target UUID plus recorded state, `complete`, and—on
refusal—the failed target UUID and generic error code. Existing immutable per-item
receipts remain recovery authority; no durable batch table is added initially.

## Safety and compatibility

The executor contacts no provider, reads no source bytes and changes no mailbox. An
attachment plan cannot bridge a message first; a document plan cannot bridge its
attachment first. The accepted one-item transactions continue to enforce current
parent pointers, completed approvals, provenance, idempotency, tenant isolation and
append-only publication. Existing one-item commands remain unchanged.

## Acceptance and rollback

Tests must prove closed schema and canonical digest validation, private-file and
revision enforcement, duplicate/bound/kind refusal, non-consuming check, exact kind
dispatch, reauthorization between items, fail-stop behavior, unchanged-plan replay,
account fencing and content-free errors. Real PostgreSQL must inject a mid-attachment
batch refusal and prove exact retry, then execute and replay an approved-document plan
without changing legacy evidence. Hosted CI and populated restore must remain green.
Rollback removes only the plan model and batch controller/command.

Design revision `2825529` and runtime revision `c143e0c` passed
[CI 35774641187](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35774641187)
and [restore 35774641102](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35774641102).
