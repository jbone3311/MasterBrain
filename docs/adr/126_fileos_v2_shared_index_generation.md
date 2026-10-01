# ADR-126 — Build FileOS v2 generations in the shared DataCore index

Status: accepted for synthetic/disposable implementation; no v2 activation.

## Context

ADR-125 can publish normalized documents on the prepared versions of one
completed FileOS v2 baseline and seal an exact ready/blocked outcome attempt.
That is historical evidence, not a searchable current generation. ADR-058's
immutable generation tables and lexical search already form DataCore's shared
index primitive, but their generation parent is required to name a v1
completed-run receipt. Pretending that a v2 completion is a v1 run would lose
policy and source provenance. A parallel v2 search index would instead fork
the common chunking, closure and retrieval machinery. The pinned FOS-Master
donor remains unchanged at `218d5caec2f20b9047fd3eb8e027dc671acf0c15`.

## Decision

- Extend the existing immutable `brain_index_generations` parent with an
  explicit, exactly-one-of-v1-or-v2 basis. Existing rows remain v1 with the
  same identities and behavior. A v2 generation binds one completion, stage,
  source and **ready** document attempt by composite foreign key. It does not
  invent a v1 run ID or modify v1 completion, absence or source pointers.
- Reuse the existing generation-item, generation-chunk and readiness tables.
  The v2 generation has exactly one item for each **hashed** attempt item,
  with identical prepared version, evidence, outcome and document identities.
  `extracted` has the exact document; all other outcomes are `not_indexed`.
  Deferred, excluded and error inventory rows remain explicitly accounted in
  their immutable staged ledger, not falsely given versions or index items.
  The generation records the completed stage's full count map and its digest
  so a future visibility decision can inspect those nonindexed states.
- A private worker-only builder requires distinct
  `brain.fileos.transition.index`, `brain.document.publish` and
  `brain.changes.read` scopes. It takes the FileOS source lock, checks the
  current v1 baseline against the completed v2 basis, the completion digest,
  the ready attempt digest and exact attempt-item ledger, then derives chunks
  from the already-published normalized bodies. It does not reopen source
  files, rerun extraction or call a model. Existing document IDs, body digests,
  deterministic chunk IDs and bounds are revalidated. An identical request
  replays the ready generation; a different code/chunker plan creates a
  separately identified immutable generation and cannot replace the first.
- Extend PostgreSQL readiness validation to close the v2 generation against
  the exact attempt items, documents and immutable `brain_chunks` set, not
  just declared counts.
  The v1 readiness branch remains unchanged. Source locks cover generation
  children and receipts even if a competing parent is not yet visible, so a
  late child cannot slip in after readiness. SQL guards reject direct
  insertion against a stale v1 baseline or unready attempt. Existing
  forced RLS, tenant-login fencing, append-only protection, protected
  truncation and runtime least-privilege grants apply to the expanded common
  tables.
- A database guard rejects **all v2 generation activations**, including
  direct SQL inserts. Current FileOS search, v1 activations, Brain API routes,
  global current retrieval and absence continue to use v1. No v2 operator
  command or LLM-facing route is added in this tranche. A later ADR must
  define explicit owner-reviewed activation, current-policy selection,
  later v2 runs, cross-policy absence and rollback before relaxing the guard.

## Safety and acceptance

The builder is bounded by the existing 64 MiB normalized-text and 100,000
chunk limits; extend the item cap to the v2 stage's 20,000-row maximum without
relaxing those text/chunk limits. A v2 generation with no hashed rows may be
ready with zero documents but still has no current-read authority. A blocked
document attempt, missing row, wrong document/evidence, body tampering, stale
v1 run, wrong tenant, direct-SQL forged readiness, late child insert or
attempted activation must fail closed. A crash before the readiness receipt
leaves no committed partial generation. Exact replay, concurrent builders,
v1 generation/activation/search regression, 3,000-row stress, populated
upgrade/restore, strict runtime, full CI and pinned-donor parity are required.

Rollback stops the private v2 builder and leaves immutable historical evidence
and generations for audit. No v2 generation becomes current; v1 and FOS-Master
remain the operational read paths. This decision is not live-root acceptance,
policy cutover, absence authority or permission to retire the donor.
