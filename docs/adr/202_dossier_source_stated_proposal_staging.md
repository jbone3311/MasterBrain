# ADR-202 — Source-stated dossier rows into the private Knowledge proposal queue

Status: accepted for synthetic-only implementation after ADR-201's merged-main
gate. No live source, inferred assertion, automatic approval, or FileOS cutover
is authorized.

## Context

The owner chose MasterBrain's ADR-197 Markdown export as the Librarian exchange
format. ADR-200 parses its fixed envelope; ADR-201 checks each claimed quote
preview against current authorized evidence. The export is not a complete
publication payload: it omits observed time, full quote, confidence, complete
evidence links, valid-time fields and reviewer identity. ADR-186 already holds
typed source-stated assertions in an immutable private queue with explicit
human decisions. A Markdown upload must not bypass that queue or use its
recorded cutoff as an invented observation time.

## Decision

1. Add a human-only `POST /v1/knowledge/dossier-markdown/proposal-batches`
   requiring `knowledge.review`, `brain.content.read` and a UUID idempotency
   key. The body contains only the exact bounded Markdown and 1–50 selected
   `(claimed_id, typed assertion payload)` pairs. A selection supplies all
   fields missing from Markdown explicitly, including the full source quote,
   observed time, confidence and complete evidence IDs; `reviewed` is
   forbidden. No server-side LLM, filesystem path, URL or provider access is
   accepted.
2. The first tranche accepts project, event and commitment rows only. Their
   sidecar payloads must match **exactly** the existing renderer's visible
   fields and quote preview for their selected row. Reject unrendered alias,
   supersession, valid-time and event-end claims; reject existing claimed IDs
   and ambiguous/mismatched project links. Claimed IDs identify source rows;
   they are not reserved publication IDs. Approval creates new MasterBrain IDs.
   An event or commitment must link to an already existing local project;
   importing a project row in the same batch cannot satisfy that dependency.
   Members, facts and artifact links
   remain readable in the inventory but cannot stage through this route until
   their typed basis and queue contracts are separately specified. No
   unsupported row is silently omitted from a selected batch.
3. In the same transaction that creates the ADR-186 batch, recheck every
   selected full quote in its **specifically cited** current, active, granted,
   nonexcluded normalized evidence, as well as every assertion's complete
   direct evidence set. A preceding ADR-201 inspection is not a durable grant;
   the stage operation must not rely on its result. Any invalid row rolls back
   all rows, leaving no proposal batch or reviewed assertion.
4. Add a nullable, immutable `import_context_sha256` to the batch header.
   Existing generic batches remain unchanged. Imported batches bind the
   canonical SHA-256 of the exact Markdown bytes and ordered selected claimed
   IDs/citations to the canonical typed payload digest. The same actor/key
   with changed Markdown, selection or payload conflicts; exact replay is
   unchanged. Store no raw Markdown, quote or file path in the import context.
   Preview exposes the digest and `untrusted_content=true`, never marks a
   proposal reviewed. The ordinary ADR-186 explicit per-row human review is
   the only path to publication.

## Verification and rollback

Use fictional Email and FileOS evidence and disposable PostgreSQL only. Prove
one and multi-row stage, zero reviewed rows before decision, exact replay and
changed-context conflict, selected-row/visible-field mismatch, fake/shortened
full quote, wrong cited evidence, stale/excluded/revoked/wrong-tenant source,
existing claimed ID refusal, assistant/scope denial, all-or-nothing rollback,
atomic approve/reject, RLS/mutation/TRUNCATE refusal and populated restore.
Run full local and hosted gates. Rollback disables the route; retain immutable
batch headers/proposals/decisions and the nullable digest column for audit.
FOS-Master stays untouched.
