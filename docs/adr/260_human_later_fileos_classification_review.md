# ADR-260 — Bounded human inspection of later FileOS classifications

Status: accepted for synthetic/disposable, historical read-only implementation.

## Context

ADR-259 compares search results and exposes aggregate review flags, but a
possible-absence or coverage flag is not reviewable without seeing which
prior files were classified. ADR-254 already seals exact prior-row
classifications in an immutable coverage closure. They must be exposed
without treating a classifier output as proof of deletion or granting
current FileOS authority.

## Decision

1. Add a human-only, source-bound Brain API page over the exact prior rows of
   one named ready historical later generation. Reuse ADR-259's source lock,
   three scopes, source-grant check, completed-run validation, latest v1/root
   check and active-source check. Independently revalidate the immutable
   ADR-254 closure before returning rows.
2. A closed request takes `generation_id`, optional exact classification
   `state`, `offset` (0–20,000) and `limit` (1–100). Rows remain in the
   closure's deterministic locator order. The response includes the run ID,
   complete classification counts, review flags, exact page, total and
   `next_offset`. Opaque prior/next version IDs and relative locators are
   untrusted source metadata; no file bytes or root path are returned.
3. Every response fixes `candidate_visibility=historical_preview`,
   `absence_authorized=false` and `current_read_active=false`. A row in
   `absence_candidate` is an observed discrepancy, never a deletion event.
   No reviewer decision, activation, current search, source effect or donor
   change is performed. A future decision must bind an owner's explicit
   adjudication to an exact generation/run and a fresh source observation;
   rollback and live-shadow gates remain separate.

## Verification and rollback

On fictional PostgreSQL data, page an unchanged run and an exact
`absence_candidate` row from a later run. Check filter/count consistency,
closed bounds, unknown generation, human/worker and source-grant denials,
and unchanged current search/absence authority. The existing 3,000-row
fictional later-generation stress case now checks its final 100-row page,
counts and an empty absence filter; this is a scale check, not a live SLA.
Run the full local and hosted gates. Rollback removes only the read route;
the immutable coverage and run remain historical. FOS-Master stays unchanged.
