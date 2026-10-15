# Librarian Markdown interoperability review

Status: design review with a bounded synthetic-only export, ADR-200's
candidate inventory parser and ADR-201's current-evidence inspection, not
proposal staging or a complete round
trip. Originally reviewed
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
| [#177](https://github.com/jbone3311/MasterBrain/issues/177) Derivation | Partial: ADR-195 project facts have a first-class `derivation`, currently constrained to `source_stated`; other assertion kinds do not have a common derivation contract. Confidence/status are not derivation. | Cover all relevant assertion kinds. Keep source-stated quotes mandatory. An inference without a direct quote needs typed links to reviewed basis assertions *and* their evidence, with transitive source-grant checks. Never put an assertion ID in `knowledge_evidence.evidence_id` or use `stance=context` as a substitute for a typed basis link. |
| [#178](https://github.com/jbone3311/MasterBrain/issues/178) Proposal queue | ADR-186 adds a private source-stated Knowledge queue and atomic, explicit per-row human review. It is not wired to Markdown, inferred claims or model suggestions. | Feed a separately specified, synthetic-only Markdown importer into this queue after an owner-approved sanitized format; add typed inference/basis handling in its own gate. No unreviewed proposal enters search, dossier or assistant retrieval. |
| [#179](https://github.com/jbone3311/MasterBrain/issues/179) Amounts, owners, fuzzy dates | Partial: claims have a value type; commitments have one optional owner and one exact due instant. | Add exact decimal + unit/currency with validation, an evidence-linked multi-owner association, and raw due wording plus an optional reviewed window/timezone. Preserve `due_at` semantics. A fuzzy interval needs an explicit overlap query contract; do not silently change ADR-161's exact-time due view. |
| [#180](https://github.com/jbone3311/MasterBrain/issues/180) Markdown dossier | ADR-162/183/194 return bounded JSON for an exact reviewed project. ADR-195/196 add source-stated facts and a fact-only export. ADR-197 adds a merged synthetic-only, bounded, fail-closed cited Markdown view across project, events, commitments, roles, related artifact occurrences and source-stated facts. | A full Librarian round trip still needs a proposal-only importer, owner-approved exchange format, typed inferred basis, richer file occurrence metadata and an explicit policy for projects exceeding one export bound. Every exported factual line needs a current authorized citation; inference must never invent a direct quote. Keep machine round-trip IDs in an authorized sidecar/manifest rather than an unbounded hidden YAML block in shareable prose. |
| [#181](https://github.com/jbone3311/MasterBrain/issues/181) Spreadsheets | **Incorrectly marked missing.** FileOS already extracts bounded CSV text and isolated XLSX cached values (ADRs 049/053); archive XLSX is also supported. | The gap is structured table/cell locators and a separately authorized Email-attachment extraction route. Reuse the isolated parser; never evaluate formulas/macros or claim that absent cached values were extracted. Preserve per-source status and limits. |
| [#182](https://github.com/jbone3311/MasterBrain/issues/182) Attachment index | Partial: ADR-065/migration 0021 create distinct child items, evidence and parent part links per Email attachment occurrence; ADR-193 adds a reviewed project link to one such evidence ID and ADR-194 shows it in the dossier under current grants. | Add richer occurrence/parent metadata reads. **Do not collapse same-hash occurrences into one artifact:** dedupe shared bytes/index work if safe, but retain every message/attachment occurrence and its provenance. |
| [#183](https://github.com/jbone3311/MasterBrain/issues/183) Fact-name registry | Missing; claim predicates and event types are constrained slugs, not a controlled vocabulary. | Version a small vocabulary with aliases and typed/unit constraints. Begin in advisory/proposal mode so existing reviewed writes and history are not invalidated. Require an explicit compatibility/migration ADR before strict rejection. |
| [#184](https://github.com/jbone3311/MasterBrain/issues/184) Exclusions | Partial: FileOS has an inventory/exclusion ledger (ADR-097). ADR-184 now filters an exact Email mailbox set before content fetch, and ADR-185 hides retained Brain/reviewed Knowledge reads for older excluded mail. | Sender/category rules, policy changes on used accounts, historical access, purge/retention and live-provider acceptance remain open. Never interpret a newly excluded FileOS path as a deletion. |
| [#185](https://github.com/jbone3311/MasterBrain/issues/185) Freshness/conflicts | Partial: FileOS completion receipts and `contradicts` evidence stance exist, but no certified project-level flag. | Freshness must derive from completed source coverage and observed checkpoints, not merely “no new evidence for N days.” Contradiction detection may flag candidate collisions among source-visible reviewed leaves; it must preserve both claims and avoid declaring a winner. Owner judgment is separate. |
| [#186](https://github.com/jbone3311/MasterBrain/issues/186) Code-first ADR | Principle exists in ADR-006 and current architecture but was not specific to Librarian exchange. | ADR-169 records the import/export boundary and is the first incorporated tranche. A static import check alone cannot prove no model influence; behavioral tests must prove the pipeline works with model access disabled. |

## Build sequence and gates

ADR-192 now checks each project-alias quote in the *proposal* queue against
its own evidence at stage, preview and review. It does not certify historical
direct publications: that route validates linked evidence but not exact
`source_quote` spans. A Markdown renderer must check each quote against
currently authorized evidence at export time and fail closed or label an
unsupported line; it cannot assume that `reviewed` means quote-verified.

ADR-193 adds reviewed project-to-artifact evidence-occurrence links with an
exact quoted basis and a separate source-scoped, bounded link-history read.
ADR-194 includes a bounded current-authorized link-history section in the
project dossier and owner workspace. This advances issues #180 and #182, but
at that stage no complete Markdown renderer or importer was enabled. A link is a reviewed association,
not evidence that its source file is current truth or safe to rename.

[ADR-195](adr/195_source_stated_project_facts.md) implements on merged PR #228 a separate
source-stated project-fact kind rather than recasting a project as an entity.
It requires exact quote binding on new writes and current source checks before
read limits. Exact PR-head and merged-main gates passed; export-time rechecks
for older assertion kinds remain open. Inference/basis storage is a separate gate.

[ADR-196](adr/196_citation_safe_project_fact_export.md) implements the first
deterministic Markdown fragment. It rechecks each new source-stated fact's
full quote at export time under current grants, then renders a bounded,
escaped, clearly partial page. It does not certify older assertion kinds,
render a whole dossier or parse an external Librarian file.

[ADR-197](adr/197_verified_project_dossier_markdown.md) is merged as a
synthetic-only export. It verifies each older displayed assertion's stored
full quote against current authorized evidence at export time and refuses an
uncitable or overfull whole-project view. It neither imports external Markdown
nor adds inferred facts or proves source freshness.

The owner selected that current export as the Librarian exchange format.
[ADR-200](adr/200_masterbrain_dossier_format_intake.md) adds a pure,
synthetic-only reader for its fixed envelope and row inventory. The Markdown
contains only quote previews and lacks observed times, all evidence links and
other publication fields, so this inventory is explicitly untrusted and never
stages or approves a proposal. A later stage path must retrieve and recheck
current authorized evidence and require the missing fields and human review.

[ADR-201](adr/201_current_dossier_citation_inspection.md) adds an owner-only
inspection API that verifies each claimed citation and escaped quote preview
against its own current, granted, nonexcluded normalized evidence. It still
cannot recover the full quote, observation time or assertion payload and never
stages a proposal. The later write transaction must recheck the full basis; a
successful inspection is not a durable grant.

1. Existing foundations are ADR-169's code-first boundary, ADR-182/183's
   reviewed aliases and roles, ADR-186's private source-stated proposal queue,
   and ADR-193/194's reviewed artifact-link history. None is a Markdown
   importer/exporter or a current-truth guarantee.
2. ADR-195's source-stated project facts passed independent PostgreSQL/RLS,
   client/browser, exact-head full CI, strict-runtime and restore gates before
   merge. Its new fact writes check quotes and the dossier rechecks current presence.
   Keep historical direct publications unverified until each displayed citation is checked
   against currently authorized evidence at export time. Do not add inferred
   fact publication through this slice.
3. Specify a deterministic export format and build the fail-closed citation
   verifier and bounded renderer. Golden fictional tests must cover duplicate
   attachment occurrences, revoked/excluded sources, unsupported old quotes,
   truncation and byte-stable output. The renderer is not a freshness or truth
   certificate.
4. Use the owner-selected ADR-197 export layout and ADR-200's read-only
   inventory as the parser baseline. Design a separate proposal-only staging
   path into ADR-186's private queue, with current full-quote/evidence checks,
   explicit missing metadata, fictional fixtures, zero reviewed rows before
   approval and no model dependency. Pre-index exclusions must precede any
   separately authorized live fetch.
5. Design typed inference-to-reviewed-basis links with transitive evidence
   grants before accepting an inferred proposal. Never encode assertion IDs as
   `knowledge_evidence.evidence_id` or weaken stated-quote requirements. Test
   cross-tenant/revoked basis, replay and direct unreviewed-write denial.
6. In later independently gated slices, add a compatible advisory predicate
   registry, typed amounts, multi-owner commitments, uncertain-date queries,
   table/cell locators and Email-attachment extraction. Preserve existing
   exact due-window semantics and isolated CSV/XLSX parser constraints.
7. Add coverage-derived freshness and candidate-conflict **flags**, then test
   round-trip stability against a fictional known-answer corpus. Neither flag
   chooses truth or establishes live-source acceptance.

Each behavior tranche requires its own ADR, additive migration where needed,
PostgreSQL/RLS and restore tests, exact-head CI, rollback notes, and independent
review before merging. The proposal-only importer must not bypass ADR-051 or
contact live mail, files, or a remote model. FOS-Master
remains unchanged and retains its separate parity/cutover gates.
