# ADR-195 — Source-stated reviewed project facts

Status: accepted and merged in PR #228 after exact-head and independent
merged-main gates passed. This decision is not a release,
Markdown-export, inferred-fact, real-source or FileOS-cutover approval.

## Context

The exact-project dossier has independently bounded events, commitments, roles
and reviewed artifact-link history. A generic `knowledge_claim` cannot directly
name a project: its required subject is an entity. Recasting a project as an
entity would duplicate identity and silently change the meaning of existing
claims. The dossier also cannot certify historical direct-publication quotes:
the older write path checks evidence identity but not the quote's text span.

The next Librarian export needs explicit project facts, not search hits guessed
to concern a project. It must avoid presenting a merely reviewed sentence as
an exact citation.

## Decision

1. Add a distinct, append-only `project_fact` assertion whose required subject
   is one exact reviewed project ID. Its bounded predicate, typed value,
   assertion status, confidence, observation/valid intervals, reviewer,
   same-kind supersession, direct evidence IDs and exact source quote follow
   KnowledgeCore conventions. The initial write accepts only `source_stated`, human-reviewed
   facts. `inferred` and model-origin facts require a later typed basis-link
   design and may not be smuggled in through a status, empty quote or generic
   evidence locator. Existing `knowledge_claims` rows are not retyped or
   migrated.
2. The human write requires `knowledge.review` and `brain.content.read`, a
   tenant/actor-scoped idempotency key, current source grants to the project
   and every direct evidence item, and at least one exact quote occurrence in
   one of those evidence items' current normalized text. Reject NUL, invalid
   Unicode, missing/excluded/stale evidence and a quote found only in another
   tenant's text. Store which evidence ID supplied the verified quote. The
   database row and its frozen evidence-ID set remain immutable. A superseded
   prior fact must itself be visible to the reviewer. The publication path
   must not fetch or modify Email, FileOS or donor files.
3. A separately bounded project-facts read pages source-visible reviewed facts
   before limit, with an optional recorded-time cutoff and explicit retained
   versus source-visible-unsuperseded selection. A fact is visible only if its
   project passes the existing exact-project grant/exclusion predicate and
   **all** its direct evidence is current and visible under source grants and
   Email exclusion. Only a visible same-kind successor may suppress a visible
   predecessor; cross-kind corrections require a separate extension. A hidden
   row neither consumes a page slot nor changes a truncation flag. The response is compact
   metadata and evidence IDs, not a claimed verified quote or source body.
4. The exact-project dossier includes an independently bounded facts
   section using the same visibility contract and recorded cutoff. It must
   preserve the separate limits and flags of existing sections. First-party
   and provider-neutral clients validate the complete response before inert
   rendering and retain separate evidence-expansion permission. This first
   tranche is not in generic Knowledge lexical search or change feed; those
   need an independently gated inclusion and visibility design.
5. The future Markdown exporter rechecks the stored quote against currently
   authorized normalized evidence **at export time**. This is mandatory even
   for facts published by the new path, because source authorization and
   currentness can change. Historical direct assertions are never grandfathered
   into an exact-citation claim. An unsupported line is omitted or clearly
   identified as unsupported; no fabricated source citation, hidden-source
   count, or misleading completeness claim is permitted.

This first tranche does not establish a controlled predicate registry, exact
decimal/unit semantics, conflict resolution, a current-truth reducer, a
complete project roster, Markdown round trip, inference storage or a model
path. A quoted source can itself be wrong; review and citation do not certify
truth. Recorded-time cutoff is not a durable cross-request snapshot.

## Acceptance and rollback

Use fictional Email and FileOS evidence in disposable PostgreSQL. Prove
exact-quote binding; source/tenant/currentness/exclusion denial at write and
read; hidden-before-limit pagination; visible and hidden supersession;
idempotent replay/conflict; malformed text refusal; immutable/RLS/truncate
protection; independent dossier bounds; client/browser malformed-response and
inert-text handling; and populated forward migration/restore. Run the full
local and exact-head hosted gates before merge. Rollback disables the new
write/read/dossier controls while retaining immutable fact rows for audit;
neither source adapter nor FOS-Master changes.
