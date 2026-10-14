# ADR-171 — Private typed statement candidates before KnowledgeCore publication

Status: accepted for synthetic, in-memory candidates only. No runtime intake,
database table, Brain API, reviewed assertion, or live-source behavior is added.

## Context

ADR-170 established exact donor-output parity for one Streetbeat recipe, but the
donor uses binary floats, has no per-row text locator, and may report a successful
sum despite omitted lines. Those raw outputs are unsuitable as holdings or as
KnowledgeCore claims. The final product needs exact amounts and evidence drill-down
across Email and FileOS, while preserving donor behavior as a comparison baseline.

## Decision

- Introduce a source-neutral, bounded in-memory candidate projection for this
  single recipe. It requires a DataCore `EvidenceRef`, explicit Email/FileOS kind,
  and a SHA-256 digest of the extracted text. It verifies the text digest before
  parsing, records the exact donor commit and projector version, and records
  character spans into that text for each row. The
  evidence reference's *source-byte* digest is separate; this helper cannot prove
  the bytes-to-text derivation or current source grant by itself.
- Parse quantities and dollar values from the original matched strings into
  `Decimal`, never by converting donor floats. Preserve grouped transaction and
  holding rows, period, account, currency, recipe and separate cost-basis and
  unrealized values. All rows remain *proposed extraction*, not reviewed facts.
- Report `reconciled`, `mismatch`, `unreconciled`, or `incomplete`. A missing or
  malformed period/account, unmatched line inside a recognized holdings section,
  unparsed trade-entry line, invalid transaction date, empty result, or row-limit
  breach must not yield a verified-looking total. `reconciled` means only that
  the row sum falls within the donor's 2%/$1 tolerance, not that holdings are
  independently verified. A stated zero long value remains zero rather than using
  the donor's `long_value or total_market_value` fallback. This deliberate
  safety divergence does not alter ADR-170's donor-parity module.
- No account aggregation, source-tier promotion, independent corroboration, or
  financial recommendation follows from one statement. A later DB/API tranche
  must recheck tenant grants, evidence/version/hash binding, evidence spans and
  atomic publication under RLS before any owner or assistant can retrieve rows.

## Verification, observability and rollback

Fictional tests cover exact decimal conversion, source kinds, text-hash refusal,
row spans, donor comparison, duplicate rows, zero/unknown totals, missing fields,
unparsed rows, invalid dates, size/row limits and 1,000-row stress. Exceptions and
status codes must be content-free; no production telemetry or source access is
introduced. Rollback removes this standalone helper and tests; no stored data or
FOS-Master state changes. FOS cutover remains barred.
