# Librarian Markdown interoperability review

Status: design review, not an implemented importer or exporter. Originally reviewed
against `main` at `8d053d8` on 2026-10-14; ADR-182 later implements the
project-alias slice. The [umbrella issue](https://github.com/jbone3311/MasterBrain/issues/174)
and its twelve children are proposals, not evidence that a capability works. This
review keeps ADR-051's human-review requirement, source-scoped reads, immutable
evidence, and synthetic-only acceptance intact.
The umbrella's “~80%” coverage estimate is not a measured acceptance result;
the implemented boundaries below are the useful baseline.

## Intended exchange

A Librarian file is one Markdown dossier per deal, person, or topic. It may contain
summaries, named participants and roles, facts, a timeline, commitments, related
artifacts, source citations, and explicitly marked interpretations. Import is a
proposal-producing operation, never a direct KnowledgeCore publication. Export is
a deterministic rendering of authorized, reviewed records, not a freshness or
truth certificate. A round trip must preserve provenance and the distinction
between source statements, human interpretations, and model suggestions.

The code-first rule is [ADR-169](adr/169_code_first_librarian_interop.md): bounded
deterministic extraction and parsing precede any optional model judgment. No model
may authorize a write, certify a conflict, supply a fabricated quote, or turn
excluded content into an indexed artifact.

## Issue-by-issue disposition

| Issue | Verified baseline | Refined direction |
|---|---|---|
| [#175](https://github.com/jbone3311/MasterBrain/issues/175) Project aliases | ADR-182 adds reviewed, evidence-linked project aliases and ambiguous, source-scoped candidate lookup. Older projects keep exact-title fallback. | A complete dossier is still missing. An alias names a project; it does not assert that a legal-entity record is the same object or auto-merge projects. |
| [#176](https://github.com/jbone3311/MasterBrain/issues/176) Deal roles | ADR-183 adds reviewed, append-only person/organization-to-project role assertions with valid time, evidence, reviewer, supersession, corrections and source-grant-safe dossier/client/browser reads. | Registry validation and a computed current roster remain separate. Bounded role slugs are not permissions; unknown syntactically valid slugs remain possible until the registry exists. |
| [#177](https://github.com/jbone3311/MasterBrain/issues/177) Derivation | Missing as a first-class attribute; confidence/status are not derivation. | Cover all relevant assertion kinds, not only four. Keep source-stated quotes mandatory. An inference without a direct quote needs typed links to reviewed basis assertions *and* their evidence, with transitive source-grant checks. Never put an assertion ID in `knowledge_evidence.evidence_id` or use `stance=context` as a substitute for a typed basis link. |
| [#178](https://github.com/jbone3311/MasterBrain/issues/178) Proposal queue | Missing for KnowledgeCore; Email has a different rule-proposal workflow. | Stage imported/model suggestions in a separate private table. A human explicitly selects and reviews each row, even in one batch request; the batch transaction is atomic, idempotent, and records per-row decisions. No proposal enters reviewed search, dossier, or assistant retrieval. |
| [#179](https://github.com/jbone3311/MasterBrain/issues/179) Amounts, owners, fuzzy dates | Partial: claims have a value type; commitments have one optional owner and one exact due instant. | Add exact decimal + unit/currency with validation, an evidence-linked multi-owner association, and raw due wording plus an optional reviewed window/timezone. Preserve `due_at` semantics. A fuzzy interval needs an explicit overlap query contract; do not silently change ADR-161's exact-time due view. |
| [#180](https://github.com/jbone3311/MasterBrain/issues/180) Markdown dossier | Partial: ADR-162/183 return bounded JSON for an exact reviewed project, with events, commitments and roles; ADR-163's `/brain` view renders them. | Add source-scoped, paginated facts and artifacts before a deterministic renderer. Each factual line cites visible evidence. Inferred lines name basis citations and say `inferred`; they must not invent a direct quote. Keep machine round-trip IDs in an authorized sidecar/manifest rather than an unbounded hidden YAML block in shareable prose. |
| [#181](https://github.com/jbone3311/MasterBrain/issues/181) Spreadsheets | **Incorrectly marked missing.** FileOS already extracts bounded CSV text and isolated XLSX cached values (ADRs 049/053); archive XLSX is also supported. | The gap is structured table/cell locators and a separately authorized Email-attachment extraction route. Reuse the isolated parser; never evaluate formulas/macros or claim that absent cached values were extracted. Preserve per-source status and limits. |
| [#182](https://github.com/jbone3311/MasterBrain/issues/182) Attachment index | Partial: ADR-065/migration 0021 already create distinct child items, evidence and parent part links per Email attachment occurrence. | Add project-artifact associations and source metadata reads under grants. **Do not collapse same-hash occurrences into one artifact:** dedupe shared bytes/index work if safe, but retain every message/attachment occurrence and its provenance. |
| [#183](https://github.com/jbone3311/MasterBrain/issues/183) Fact-name registry | Missing; claim predicates and event types are constrained slugs, not a controlled vocabulary. | Version a small vocabulary with aliases and typed/unit constraints. Begin in advisory/proposal mode so existing reviewed writes and history are not invalidated. Require an explicit compatibility/migration ADR before strict rejection. |
| [#184](https://github.com/jbone3311/MasterBrain/issues/184) Exclusions | Partial: FileOS has an inventory/exclusion ledger (ADR-097); there is no equivalent Email label/folder pre-fetch policy. | Enforce source-specific exclusions **before content fetch or extraction**, and before indexing. Record content-free policy/count receipts; do not hash excluded content. Changes to policy and any retroactive purge are separate owner-reviewed operations. Never interpret a newly excluded FileOS path as a deletion. This is a prerequisite to a live-source import, not a late polish step. |
| [#185](https://github.com/jbone3311/MasterBrain/issues/185) Freshness/conflicts | Partial: FileOS completion receipts and `contradicts` evidence stance exist, but no certified project-level flag. | Freshness must derive from completed source coverage and observed checkpoints, not merely “no new evidence for N days.” Contradiction detection may flag candidate collisions among source-visible reviewed leaves; it must preserve both claims and avoid declaring a winner. Owner judgment is separate. |
| [#186](https://github.com/jbone3311/MasterBrain/issues/186) Code-first ADR | Principle exists in ADR-006 and current architecture but was not specific to Librarian exchange. | ADR-169 records the import/export boundary and is the first incorporated tranche. A static import check alone cannot prove no model influence; behavioral tests must prove the pipeline works with model access disabled. |

## Build sequence and gates

1. Adopt ADR-169 and this corrected contract. This is documentation only; no
   importer, approval queue, or model path is claimed.
2. Specify the staged import format, citations/basis links, exclusions, privacy
   bounds, and explicit row-selection/batch-review contract in a separate ADR.
   First obtain an owner-approved, sanitized example of the actual Librarian
   Markdown layout; the review prompt alone does not define a parseable grammar.
   Build the proposal-only importer with a fictional Markdown fixture and prove
   zero reviewed rows before approval. Exclusion rules must precede **any**
   authorized live fetch; the synthetic importer may use only its explicit file.
3. Add derivation/basis storage and transitive source-grant checks. Only then add
   atomic human batch approval through the existing reviewed publication path.
   Test cross-tenant and revoked-source basis links, replay, rollback, malformed
   citations, and direct unreviewed-write denial.
4. ADR-182 adds project aliases independently because it is an additive,
   reviewed write and read boundary with no import path. Add membership/role
   assertions next, then the compatible predicate registry. Test superseded
   roles before any automated entity matching. The proposal-only importer in
   step 2 remains the first *import* tranche and still needs a sanitized layout.
5. Add typed amounts, multi-owner commitments and an explicit uncertain-due
   query; preserve exact due-window compatibility. Reuse FileOS CSV/XLSX
   extraction to add bounded table/cell locators and a separate Email route.
6. Add project-artifact links and a bounded Markdown export over authorized
   reviewed records. Golden export/import/export tests must prove provenance,
   duplicate occurrences, hidden-source denial, truncation, and stable rendering.
7. Add coverage-derived freshness and conflict **flags**, then evaluate against
   a fictional known-answer corpus. Neither flag is a truth or live-source claim.

Each behavior tranche requires its own ADR, additive migration where needed,
PostgreSQL/RLS and restore tests, exact-head CI, rollback notes, and independent
review before merging. The proposal-only importer must not bypass ADR-051 or
contact live mail, files, or a remote model. FOS-Master
remains unchanged and retains its separate parity/cutover gates.
