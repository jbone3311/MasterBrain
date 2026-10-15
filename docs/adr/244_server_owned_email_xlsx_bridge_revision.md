# ADR-244 — Server-owned Email XLSX bridge revision

Status: implemented on an open PR with fictional PostgreSQL coverage and a local populated restore pass at `0c64f8b`. Actual-image execution, hosted exact-head CI and independent review remain open.

## Context

ADR-242's publication-review request let the human caller supply `code_revision`, then copied that value into the DataCore provenance and bridge receipt. A reviewer can authorize an exact result digest and counts but cannot attest which server transform code executes. Treating the caller's string as code provenance was a false claim.

## Decision

The bridge owns the semantic transform revision `email-xlsx-document-bridge-v2`. Remove `code_revision` from the human API request and from the review service arguments. The service writes its own revision into the immutable review, its idempotency digest, document provenance and publication receipt. A worker refuses a review with a different revision before publication. Migration 0086 adds insert guards to both the review and receipt tables so direct SQL cannot create a new caller-chosen revision. It preserves existing rows from migration 0085; old reviews with another revision cannot be newly published by this bridge and require a fresh exact extraction approval/review. The revision names a versioned transform contract, not a Git commit or a financial attestation.

The human still verifies extracted text, SHA-256 and counts through ADR-242's bounded inspection route. No source bytes, live account, FileOS policy or KnowledgeCore fact status change.

## Acceptance

Fictional API tests reject a `code_revision` field and confirm the server revision on the stored receipt. PostgreSQL rejects a forged review revision, while existing digest/count, source-currentness, owner and SQL chunk guards continue to pass. Historical migration, recovery and protected-table checks must pass. Full-suite, actual-image, hosted CI and independent restore are separate gates.
