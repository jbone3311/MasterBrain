# ADR-085 — Require archive-document preview before batch design

Status: accepted design; implementation pending.

## Context

The one-document command is explicit and safe, but an owner needs a bounded view of
eligible document members and publication state before manually selecting work.
Jumping directly to archive-wide extraction would combine discovery, key allocation,
two restricted workers and mutation, making authorization and partial failure harder
to review.

## Decision

Add an owner-private, ordinal-cursor preview for one explicitly named current archive
inventory. Return only exact PDF/DOCX/XLSX candidates accepted by the existing
document selector plus their already-published label. Reuse the closed private
configuration and scopes while performing no source read, member read, worker
construction or write. Treat returned virtual locators as untrusted private metadata.

Do not authorize a batch schema or executor in this checkpoint. Any future batch must
be a separately reviewed, digest-bound plan with caller-supplied stable keys and
explicit fail-stop/resume semantics across both worker boundaries.

## Alternatives rejected

- Automatically extract every document: grants unreviewed expensive fan-out.
- Reuse the text-member preview: its eligibility, size and container rules differ.
- Generate retry keys in preview: blurs read-only review and execution authority.
- Return every unsupported member: expands metadata disclosure without serving the
  current command.
- Add a public Brain API route: exposes operator discovery beyond its intended trust
  boundary.

## Rollback

Remove the preview query, controller and command. Existing inventories, one-document
publication, current/retained search and source state remain unchanged.
