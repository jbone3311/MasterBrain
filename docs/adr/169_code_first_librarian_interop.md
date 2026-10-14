# ADR-169 — Code-first Librarian interoperability boundary

Status: accepted design principle on 2026-10-14; no importer, exporter, schema,
model adapter, or live-source behavior is implemented by this ADR.

## Context

MasterBrain needs to exchange one-file-per-topic Markdown dossiers with a
file-based Librarian workflow without making either format authoritative over
immutable source evidence. ADR-006 prefers deterministic processing; ADR-051
requires human-reviewed, evidence-linked KnowledgeCore publication. The
[interop review](../LIBRARIAN_INTEROP.md) identifies gaps and corrects several
proposals that would otherwise misstate existing extraction or provenance.

## Decision

- Deterministic, bounded code owns intake, parsing, normalization, text/table
  extraction, hashes, dedupe signals, dates and exact decimal amounts, candidate
  entity matching, citation resolution, exclusions, and export rendering. It
  records uncertain or unsupported outcomes; it never fabricates a value.
- Optional LLM output is limited to judgments such as summaries, opinions,
  inferences, or suggested conflict resolutions. It is untrusted proposal data,
  marked inferred with model/version and basis provenance. It cannot approve
  itself, supply a false direct source quote, or authorize source effects.
- Import creates private proposals only. ADR-051's reviewed tables remain
  unchanged until a human explicitly accepts selected rows through a separately
  designed, idempotent review path. A batch is an ergonomic selection, not
  blanket approval. Existing `knowledge.review` and assistant restrictions hold.
- A source-stated fact needs an exact evidence citation and quote. An inference
  without a direct quote needs typed reviewed-assertion/evidence basis links,
  explicit labeling, and source-grant checks along the entire basis chain.
  Inference is not a new stance of `knowledge_evidence`.
- Exclusion policy applies before source content is fetched, extracted or
  indexed. Excluded content cannot be sent to a model. Source-specific policies
  may differ, but their effective version and content-free outcomes are auditable.
- Exports include only authorized reviewed records, label partial coverage and
  uncertified freshness, and never silently flatten contradictory claims or
  duplicate attachment occurrences. Machine identity for round trips belongs
  in a bounded, separately authorized manifest.

## Verification before behavior is accepted

Use only fictional fixtures. Prove a deterministic import/export path with model
access disabled; exact citations and no invented quote; zero reviewed writes on
import; explicit, atomic and replay-safe row approval; tenant and transitive
source-grant isolation; exclusion before fetch; stable authorized rendering;
bounded malformed-input handling; and a populated no-rewrite restore. A static
dependency/import check may supplement these tests, but cannot replace them.

## Consequences and rollback

The rule narrows future implementation choices; it does not provide a working
Librarian product by itself. Each schema, API, approval, or exclusion behavior
still needs its own ADR and migration review. Rollback of this documentation
changes no stored data or source state. FOS-Master and live sources are untouched.
