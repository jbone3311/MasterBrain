# ADR-159 — Review-chain leaves in grouped current Brain reads

Status: accepted for a synthetic/disposable read-only candidate, pending PR
verification. No hosted or live-source acceptance follows.

## Context

ADR-158 added an explicit, source-grant-aware `unsuperseded` KnowledgeCore
search. The grouped `/v1/brain/current-search` route still calls the retained
default and labels its Knowledge layer `reviewed_retained_assertions`. Ask
reuses that grouped current route, so a superseded or explicitly corrected
reviewed assertion may appear next to current Email/FileOS evidence without a
clear historical label. The direct KnowledgeCore and unified-search routes
must continue to support forensic retained history.

## Decision

- Use ADR-158's `unsuperseded` visibility only for the Knowledge layer of
  `/v1/brain/current-search` when `source_focus=all`. Ask inherits this
  projection through the same route. Focused Email or FileOS calls continue
  to skip KnowledgeCore entirely. The direct KnowledgeCore default and
  `/v1/brain/unified-search` remain retained-history compatible.
- Label grouped coverage `reviewed_unsuperseded_assertions`. This is a
  review-chain leaf projection, **not** a claim that the assertion is valid
  now, fresh against its source, uncontradicted or true. Keep independent
  layer ranks, partial coverage and source-grant filtering. Multiple leaves
  remain separate; do not silently resolve conflicts.
- Preserve the existing AnswerService recheck: if a selected reviewed match
  disappears or changes between the first and final grouped reads, refuse a
  stale answer. No new authority, database migration, original-evidence
  access, model synthesis or source effect is introduced.

## Verification and rollback

Test owner and assistant grouped reads over supersession, corrections,
source-hidden successors and multiple branches; check that retained direct
and unified reads still include history. Test Ask's reviewed list and focused
skip behavior, schema/coverage labels, and the full PostgreSQL, runtime,
restore and documentation gates. Roll back the grouped call to `retained`
and its coverage label if the projection fails acceptance; keep ADR-158's
optional direct mode and immutable review history. FOS-Master is unaffected.
