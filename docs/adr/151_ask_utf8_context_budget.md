# ADR-151 — Explicit UTF-8 budget for extractive Ask context

Status: accepted for the synthetic/disposable read-only Ask path.

## Context

ADR-134 bounds the selector to eight passages of 1,200 characters each.
Unicode characters can occupy four UTF-8 bytes, so this is not a byte budget
for a future model adapter. The local selector also needs to avoid implying a
complete search when a passage was cut for compactness.

## Decision

- Retain the existing 1,200-character evidence read and eight-passage ceiling.
  Before selector invocation, cap each passage at 2,048 UTF-8 bytes and all
  passage text together at 8,192 UTF-8 bytes. Truncate only at a valid Unicode
  boundary and keep the original document digest and evidence identity; no
  stored evidence or index is rewritten. The API question remains separately
  limited to 500 characters. These are hard byte ceilings, not tokenizer-based
  token counts or permission to send content to a remote model.
- Preserve candidate order and source-grant/currentness checks. Once the
  aggregate budget is exhausted, do not read or pass further candidate text.
  Surface `coverage.answer_context_truncated` when the upstream 1,200-character
  read or this byte budget shortened a candidate, or the byte budget omitted
  one. An empty/unsupported answer under this flag is not a claim that
  no other source text could support the question.
- Reject malformed non-UTF-8 text from an adapter rather than silently
  transforming it. The selector still returns only exact quotes from the
  bounded passage, verified again against current evidence and grants.
- No new tool, scope, storage, remote inference, source effect, FileOS cutover
  or hosted acceptance is authorized.

## Verification and rollback

Test multibyte boundaries, per-passage and aggregate limits, omitted candidates,
exact citation offsets, client/browser coverage visibility, malformed text and
revocation after selection. Run local PostgreSQL, browser, full CI, strict
runtime, restore and documentation gates. Roll back the code-only cap with a
reviewed deployment; no evidence migration or source compensation is needed.
Passing this gate does not establish a full model-token budget, total response
envelope bound or a certified external assistant.
