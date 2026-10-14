# ADR-188 — Narrow source-byte to text derivation proof

Status: accepted as a synthetic-only, pure verification primitive. It is not
connected to the statement proposal worker, owner preview, a live source, or
reviewed KnowledgeCore publication.

## Context

ADR-172 checks that a statement proposal's source version, evidence and
normalized text each match their stored hashes. It does not prove that the
normalized text was actually produced from those source bytes. A fictional
test fixture intentionally stores a valid source-byte digest beside unrelated
valid text. Hash consistency alone must never be called derivation proof.

## Decision

- Add a bounded, content-free proof value for the exact DataCore `fileos-text-v1`
  transformation of text, Markdown, HTML and CSV source bytes. Replay the same
  extractor on supplied bytes; require exact source size/digest, exact normalized
  text/digest and the pinned normalizer version. Reject missing, malformed,
  oversize, unsupported, ambiguous-encoding, empty and mismatched inputs.
- This pure function does no filesystem or provider read and grants no source
  authority. A future worker must independently obtain bytes through the
  authorized current-version source boundary, recheck tenant/source grants and
  version freshness, and durably bind the proof to a proposal before any row can
  be represented as source-derived. The existing ADR-172 proposal path remains
  **unverified** and unchanged by this tranche.
- PDF, Office, OCR, Email attachment and archive transformations require their
  own exact-version isolated replay/receipt contracts. Their source digests and
  normalized text hashes are not substitutes for such proof. No model output or
  donor recipe receives authority from this primitive.

## Verification and rollback

Fictional tests cover exact UTF-8/BOM, Markdown, HTML and CSV replay; altered
bytes, source size, text, transform version, traversal locator, unsupported
format, ambiguous encoding, NUL, empty and over-bound refusal. No personal
mail or FileOS root is read. Rollback removes the unused primitive; no stored
evidence or proposal is changed.
