# ADR-157 — Aggregate output-text budget for extractive Ask

Status: accepted for the synthetic/disposable read-only Ask path.

## Context

ADR-151 caps source passages presented to the selector, but the resulting exact
quotes and separately reviewed KnowledgeCore text only have per-item character
ceilings. Four multibyte reviewed excerpts can therefore return much more
untrusted text than the input passage budget. The browser also counted UTF-16
code units where the Python API counted Unicode characters, rejecting otherwise
valid multibyte titles, excerpts and citation offsets.

## Decision

- Cap the aggregate UTF-8 bytes in returned exact quote strings plus reviewed
  title/excerpt strings at 8,192. Do not include fixed server-written answer
  boilerplate, IDs, provenance or JSON framing in that number; this is **not**
  a total response, tokenizer-aware or model prompt budget.
- Preserve all selected exact quotes and their citation offsets. The existing
  four-by-400-character quote maximum fits inside this budget even at four
  bytes per character. Allocate the remaining bytes to reviewed matches in
  stable search order. Preserve each title intact; shorten an excerpt only at
  a Unicode boundary, or omit a match if its full title and a nonempty excerpt
  cannot fit. Never emit a reviewed match with missing text or changed evidence
  links. Continue rechecking the full selected assertions and all their direct
  evidence links before applying this display budget.
- Set `coverage.answer_output_truncated` when the existing 1,200-character
  reviewed excerpt ceiling, the aggregate byte ceiling, or omission shortens
  returned reviewed text. Keep it separate from
  `coverage.answer_context_truncated`, which concerns selector input. The
  first-party UI displays both notices; the reference client and browser
  refuse malformed flags and over-budget responses.
- Count browser characters by Unicode code point for the server's character
  limits and citation offsets. Count the aggregate bytes with UTF-8 encoding.
  This does not change stored evidence, search order, scopes, source grants,
  FileOS policy or FOS-Master.

## Verification and rollback

Test multibyte boundaries, exact quote preservation, deterministic reviewed
omission/truncation, later-hit behavior after a per-item clip, malformed
Unicode, client/browser rejection and browser-visible notices. Run the full
local non-PostgreSQL suite and hosted CI, strict-runtime and restore gates.
Roll back the code-only response policy with a reviewed deployment; no schema
or source migration is involved. Held-out chat quality, total JSON/response
size, token accounting, named-assistant and hosted acceptance remain issue #92
and issue #88 work.
