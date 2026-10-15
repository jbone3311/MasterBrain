# ADR-207 — Project-artifact Markdown proposal boundary

Status: synthetic/disposable implementation on an open PR branch. The
transactional publisher and private artifact proposal stage/preview/human
review are locally tested. Hosted and merged-main gates, live source and
FileOS cutover are not accepted.

## Context

ADR-193 records an explicitly reviewed association between an exact project
and an exact Email attachment or FileOS evidence occurrence. Its independent
basis evidence may be a parent email, so the artifact ID and quote citation
must never be collapsed to a content hash or one inferred source. ADR-197's
selected MasterBrain dossier renders relation, status, artifact source kind,
artifact evidence ID, bounded basis-quote preview and basis citation. It does
not render the full quote or observation time. ADR-200/201 inspect this as
untrusted Markdown, while ADR-202/205/206 stage selected other row kinds.
The generic proposal route still refuses artifact-link rows; ADR-207's
separate route handles selected links.

The generic ADR-186 proposal decision is foreign-keyed to a Knowledge
assertion receipt. ADR-193 link publication instead creates a
`knowledge_project_artifact_receipts` row. Sharing the generic queue or the
fact-specific ADR-206 queue would weaken the approval proof or mislabel a
link as a fact. The direct artifact publisher originally owned its own
transaction; this implementation extracts a narrow caller-bound primitive.

## Decision

1. First extract ADR-193's existing validation and publication into a
   caller-transaction-bound internal primitive. The direct API keeps the
   same authorization, source/currentness/quote, idempotency, audit and
   return contracts. A failed later write must roll back earlier links and
   their receipts in that transaction. This prerequisite alone creates no
   proposal storage or importer route.
2. A later additive migration creates a **separate private artifact-link
   proposal queue**: tenant/actor-scoped 1–50 row batches, immutable typed
   payloads, selected artifact and basis evidence IDs, ordered per-row
   decisions and one atomic human review receipt. An approval must bind the
   exact ADR-193 publication receipt and resulting link ID; a rejection has
   no link. Use forced RLS, tenant-login fencing, no UPDATE/DELETE/TRUNCATE,
   tenant-composite foreign keys and deferred whole-batch closure. Preserve
   historical rows and both other proposal queues unchanged.
3. Stage only selected `artifact link` rows from the unchanged dossier
   envelope. Require a closed `ProjectArtifactLinkWrite` sidecar containing
   the **full** source quote and aware observation time. The project ID comes
   from the dossier and must be an already reviewed, currently visible local
   project. The claimed `partifact_...` ID is a selection marker, never the
   new publication ID; reject a claimed ID already present locally. Rebuild
   the entire selected line byte-for-byte from the sidecar plus the currently
   verified artifact source kind. Do not trust a Markdown kind label, a
   filename, a hash, or the recorded cutoff as publication metadata.
4. Bind exact Markdown bytes, ordered selected IDs and citations, canonical
   typed payloads and current artifact-kind observation to the immutable
   batch digest. At stage, owner-only preview and explicit human review,
   recheck project, artifact and basis separately under current source
   grants, active/current state and Email exclusions. The full quote must
   occur in the **specifically cited basis** normalized document; the
   preview alone is insufficient. Revocation of either evidence occurrence
   or the project fails closed. One bad row aborts the whole batch.
5. Every row needs an explicit approve/reject decision. Approval calls the
   same transaction-bound ADR-193 publisher and issues a new link ID and
   reviewer-bound receipt. A changed idempotency replay conflicts; no
   Markdown, parser, model or assistant can approve. Unreviewed batches are
   absent from search, dossier, changes and assistant reads. A future owner
   inbox may aggregate separate queues without merging their SQL contracts.
6. This is association history, **not** an automatic current-file roster,
   FOS source effect, inferred relationship, lossless Markdown round trip or
   real-data acceptance. `retracted` remains an explicit reviewed row, not
   an automatic negation of another link. FOS-Master stays unchanged.

Migration 0070 implements separate private forced-RLS artifact proposal,
decision and review-receipt tables. The service stages selected rows from the
existing export with a closed typed sidecar, previews under current grants and
reviews every row atomically using the extracted transaction-bound direct
publisher. The old direct route uses that same primitive. A synthetic
second-link fault rolls back the earlier link and receipt. This is not a
FileOS migration switch or a lossless dossier round trip.

## Acceptance and rollback

Use only fictional Email attachment and FileOS occurrences in disposable
PostgreSQL. Test direct-publisher regression and transaction rollback; exact
export/inspect/stage/preview/review; both same-item and separate-parent basis;
same-hash distinct occurrences; wrong artifact kind, wrong valid citation,
quote-preview/full-quote mismatch, wrong project, source revocation and
exclusion at every gate; tenant/assistant/scope refusal; claimed-ID and
idempotency conflict; mixed approve/reject and second-row fault rollback;
direct-SQL citation/receipt guards, RLS, immutability, protected TRUNCATE,
migration and populated restore. Run full local, exact-head hosted CI,
strict-runtime, independent-container restore and merged-main gates before
calling it delivered. Rollback disables new stage/preview/review routes but
retains private rows and reviewed links for audit.

The current dossier exporter bounds its artifact section to at most 25 rows;
the 1–50-row private queue does not make a 50-artifact single-export dossier
possible. Synthetic stress covers the 25-row export limit, mixed decisions,
late-fault rollback and same-hash distinct evidence occurrences. Larger
exchange requires a separately designed, provenance-preserving paging format.
