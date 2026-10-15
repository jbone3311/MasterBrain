# ADR-217 — Current-source human tier review, not byte attestation

Status: implemented for fictional local testing on an open PR; hosted CI,
independent restore and merged-main acceptance remain open.

## Context

ADR-216 preserved the donor `fact_verify.py` behavior but showed that its
filename/sender tier heuristics, substring matches and stored hashes cannot
certify MasterBrain financial claims. MasterBrain already has immutable source
versions and evidence, normalized text, current-version pointers, exclusion
policy, human-only `knowledge.review`, source grants and audit events. Those
allow a narrow human document-authority review without importing FileOS's
`CONFIRMED` status.

## Decision

Migration 0075 adds immutable, tenant-isolated `knowledge_source_tier_reviews`.
Each review pins one evidence ID, source version and recorded SHA-256, one
normalized document and its text SHA-256, an exact source quote, a controlled
T1/T2/T3 authority kind, the human reviewer and an idempotency receipt. T1 is
signed instrument/regulatory filing; T2 is issuer/administrator statement;
T3 is internal record/other. This is a **human classification of metadata and
quoted content**. It does not assert that the original bytes were independently
retrieved and rehashed, that OCR is complete, that sources corroborate a value,
that the actor owns a holding, or that a financial amount is true.

`POST /v1/knowledge/evidence/{evidence_id}/source-tier-reviews` requires a
human with `knowledge.review` and `brain.content.read`, a UUID idempotency key,
current active unexcluded evidence, source grant, matching recorded hashes and
an exact quote in the selected document. An independent SQL trigger repeats
the source/document/currentness/quote checks and binds reviewer ID to the
transaction actor. The row is append-only; a different judgment is a new row,
not a silent overwrite. `GET` on the same path requires `knowledge.search`
and `brain.content.read`, filters again against current source/grant/exclusion
and document/hash equality before a 25-row limit, reports truncation and
does not expose the quote. Multiple or conflicting human reviews remain
visible; no winner or certified tier is inferred. Reads are no-store and
untrusted-content marked. The provider-neutral read client rejects malformed
rows and any response that upgrades the meaning to financial truth.

The donor classifier is not connected to either route. No project fact,
statement row, investment balance or dossier is upgraded by a tier review.
FOS-Master stays unchanged.

## Acceptance and next gate

Fictional PostgreSQL tests cover idempotency, hash/quote binding, mismatched
tier shape, source grants, paused-source invisibility, assistant write denial,
current assistant read, direct-SQL hash/reviewer bypass attempts and immutable
rows. Full migration/RLS/recovery suites must pass against disposable
PostgreSQL. The next gate is trusted replay of authorized source bytes against
the pinned version hash and extraction coverage (including PDF/OCR), plus a
reviewed issuer/authority policy and contradiction handling. Only then may a
separate ADR define use in financial claim publication.
