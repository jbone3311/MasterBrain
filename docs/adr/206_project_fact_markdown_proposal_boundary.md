# ADR-206 — Project-fact Markdown proposal boundary

Status: design accepted for a future synthetic/disposable implementation; the
transactional publication prerequisite is implemented, but the **fact
proposal queue is not**. No live source, automatic approval, inferred fact,
or FileOS cutover is authorized.

## Context

The owner selected MasterBrain's existing ADR-197 dossier export as the
Librarian exchange format. ADR-200/201 inventory and inspect that exact
Markdown; ADR-202/205 stage selected project, event, commitment and member
rows as private proposals. A selected `fact` row is still rejected. Its
export line displays predicate, value, assertion status, derivation, a quote
preview and one citation, but omits value type, confidence, observation/valid
times, full quote and the complete direct evidence set. None of those fields
may be inferred from the recorded cutoff or from the preview.

ADR-195 intentionally stores reviewed project facts apart from the generic
Knowledge assertion tables. The existing ADR-186 proposal approval receipt
has a foreign key to `knowledge_receipts`, whereas project-fact publication
uses `knowledge_project_fact_receipts`. Merely adding `project_fact` to the
generic proposal type union would make the approval contract incorrect.

## Decision for the next implementation tranche

1. Add a **separate private project-fact proposal batch** and explicit
   per-row human review receipt, rather than weakening the existing generic
   receipt foreign key or pretending a fact is an entity claim. Reuse the
   same 1–50 row, tenant/actor-scoped UUID idempotency, immutable payload,
   digest, RLS/login fence, protected-truncate, and all-or-nothing semantics
   of ADR-186. The fact queue must not appear in search, dossiers, changes,
   or assistant reads before approval. A later unified owner inbox may show
   both queue types without conflating their storage or receipt meaning.
2. Stage only selected `fact` rows from the **unchanged** ADR-197 Markdown
   envelope. Require an explicit closed `ProjectFactWrite` sidecar with
   `reviewed` absent and `derivation=source_stated`; reject supersession and
   valid-time fields that the export cannot display. The selected line must
   be reconstructed byte-for-byte from the typed predicate, value, status,
   full-quote preview and cited evidence ID. `value_type`, confidence,
   observed time and all direct evidence IDs come only from the sidecar;
   they remain visible as untrusted proposed fields in owner preview.
3. A proposed fact must reference an **already reviewed local project**.
   Its Markdown `pfact_...` ID is only a selection marker, never an assigned
   publication ID. Reject a claimed ID already present locally. A project
   proposed in the same Markdown batch cannot satisfy the dependency; first
   review the project, then explicitly remap and stage its facts. Bind the
   exact Markdown bytes, ordered selection/citation IDs and canonical typed
   payloads into the immutable batch digest. Exact replay is stable;
   changing any bound input under the same key conflicts.
4. At stage, preview and review, recheck the whole direct evidence set for
   current, active, granted, nonexcluded versions; require the **full** quote
   in the specifically displayed `quote_evidence_id`; and recheck the local
   project under current source grants. An earlier ADR-201 inspection is not
   a durable grant. One bad row aborts the entire stage or review, not just
   that row. SQL constraints/triggers must prevent missing or unbound cited
   evidence in new imported proposal rows even for direct SQL writes.
5. Approval calls the same validated, transactional publication primitive as
   ADR-195's direct human project-fact write, generating a new `pfact_...` ID
   and a fact receipt tied to the reviewer and deterministic publication key.
   Every row must receive an explicit approve/reject decision in one
   transaction. A rejection stores a reason and no fact. Re-approval with a
   changed decision conflicts; no parser, model or batch membership approves
   anything. The direct fact route's behavior must remain unchanged.
6. Do not silently add artifact links to this queue. ADR-193's artifact
   occurrence/basis pair and its publication receipt require a separate
   design and tests. Inferred facts need typed basis-assertion links under
   ADR-177, not an empty or fabricated source quote. Automatic dossier
   generation and lossless round trip remain out of scope for this tranche.

The first prerequisite refactors ADR-195's direct publisher into an internal
transaction-bound primitive with unchanged public write semantics. A fictional
two-fact test proves that a failed later publication rolls back the first fact
and its idempotency receipt. This does **not** create a proposal table, route,
private preview or human batch-review operation.

## Acceptance and rollback

Use only fictional Email/FileOS evidence and disposable PostgreSQL. Prove
export-to-inspection-to-stage-to-preview-to-review for one fact and a mixed
approve/reject fact batch; zero pre-review exposure; exact replay and
changed-context conflict; quote-preview/full-quote mismatch; wrong cited
evidence despite a quote in another direct evidence item; missing/stale/
excluded/revoked/cross-tenant source or project; same-batch project refusal;
claimed-ID collision; malformed value, unrendered fields, assistant/scope
denial, direct-SQL guard, RLS, immutability, protected TRUNCATE, migration
and populated restore. Test revocation between stage and review, failure of
one row rolling back all decisions/publications, and reviewer-key replay.
Run the full local gate, exact-head hosted CI, strict runtime, logical restore,
and independent merged-main gate before calling it delivered. Rollback
disables the fact stage/review routes while retaining immutable proposals and
decision receipts for audit. FOS-Master is neither modified nor switched.
