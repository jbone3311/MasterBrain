# ADR-185 — Excluded Email evidence cannot leak through Brain or Knowledge reads

Status: accepted for synthetic-only implementation. This extends ADR-184; it
does not approve a real Fastmail source, retroactive purge, or FileOS cutover.

## Context

ADR-184 hides the legacy Email projection and current bridged Brain search when
an already indexed message gains an excluded mailbox. The immutable parent,
attachment and approved-document bridge evidence remains. Retained Brain search,
evidence/content and change reads, and reviewed KnowledgeCore assertions can
otherwise reveal that older content after exclusion. Source grants alone do not
answer whether an authorized source item is currently policy-excluded.

## Decision

- Add one tenant-RLS-respecting, security-invoker SQL predicate that resolves an
  exact Brain evidence ID through the three immutable Email bridge receipt
  families to its legacy message and current `message_sync_state`. It returns
  true only for `status='excluded'`; ordinary deletion, quarantine, source
  revocation and FileOS history retain their existing semantics. Lookup indexes
  bound the three evidence-ID branches. The function does not return a provider
  ID, mailbox name or source text to API callers.
- Apply the exclusion predicate inside the same transaction and SQL query,
  **before ranking, limit, pagination or disclosure**, to retained DataCore
  search, Brain evidence/content and change feeds. An excluded direct evidence
  ID or change cursor is not found. Current Email search keeps its existing
  current-message check. It does not use a post-limit Python filter.
- KnowledgeCore direct-source visibility rejects an assertion if *any* direct
  basis evidence is excluded. This is conjunctive with source grants and is
  applied transitively to related entities, projects, members, corrections,
  timeline, due commitments, aliases, dossier and grouped/grounded retrieval
  through the existing visibility helper. New reviewed assertions cannot be
  published against already excluded evidence. The retained/unsuperseded
  distinction still applies to nonexcluded evidence; exclusion is not a
  historical revision or a new source grant.
- The legacy, explicitly human-scoped historical Email evidence route remains
  available under existing audit and retention rules; this tranche does not
  silently purge or rewrite immutable records. A separate owner retention
  decision must settle whether that route should also deny excluded history.

## Proof and rollback

Use disposable PostgreSQL and fictional JMAP only. Tests cover a ready Email
bridged into DataCore and a reviewed project, its transition to excluded, no
retained Brain/Knowledge result or direct Brain evidence/content/change path,
re-entry, and a different tenant/source. Parent, attachment and document bridge
IDs must all map to the same exclusion outcome; a non-Email item and an ordinary
deleted Email retain their prior retained behavior. Exercise source-grant and
limit-before-filter attacks and keep the full FileOS donor parity suite green.

Rollback disables the scoped synthetic worker and new read routes; do not
down-migrate, remove immutable bridge receipts or reinterpret provider deletion.
Real-source acceptance still requires owner approval, complete cross-route
audit, policy-change/retention decisions and operations rehearsal.
