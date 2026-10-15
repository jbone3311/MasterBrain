# ADR-196 — Citation-safe project-fact Markdown fragment

Status: accepted, merged in PR #230 after exact-head gates. This is one
synthetic-only export tranche, not a complete Librarian dossier, live-source
acceptance, or FileOS cutover.

## Context

ADR-195 stores an exact source quote for a reviewed project fact, but the
ordinary page and dossier intentionally return only compact previews. Older
project, event, commitment, member, and artifact-link assertions do not all
have export-ready source-quote contracts. Rendering the entire dossier as
apparently cited prose would therefore overstate what has been verified.

## Decision

1. Add a separate, read-only, bounded Markdown **project-facts fragment** for
   one exact project. It requires both `knowledge.search` and
   `brain.content.read`. Enrolled assistants remain source-scoped; unknown and
   hidden projects share not-found behavior. It neither grants original bytes
   nor performs source effects.
2. In one tenant-fenced read transaction, check the project and every fact's
   complete frozen evidence set under current source grants, active/current
   versions and Email exclusions **before** ordering and limiting. Recheck
   the stored full quote in the current normalized body of its own quote
   evidence. Only source-stated reviewed facts can be rendered. A visible
   successor may suppress a visible predecessor in the default
   `unsuperseded` mode; `retained` is explicitly labelled history.
3. Return at most 25 fact lines per page, with a cutoff and visible cursor.
   Each line contains an exact project-fact ID, predicate, bounded value,
   a short prefix of the verified source quote, and the exact quote-bearing
   evidence ID. Both value and quote truncation are explicit. Render all
   untrusted strings as inert, single-line escaped Markdown; source text
   cannot introduce links, headings, HTML or another citation. The output
   has a fixed, content-free title and a conspicuous partial-coverage note.
4. The response is JSON with the Markdown fragment and closed metadata, not
   a persistent export artifact. It states that only currently visible
   source-stated project facts are represented; events, commitments, roles,
   related artifacts, inferences, source freshness and hidden sources are
   **not** certified or counted. A page without a next cursor is complete only
   for this visible fact slice, not for a whole project dossier. Never label a
   cited statement as real-world truth.
5. Record a fixed audit operation with no quote, value or project identifier.
   Do not log Markdown or source text. The cutoff is not a durable snapshot;
   every page repeats current authorization and quote checks. Revocation
   after a response cannot erase an already delivered fragment.

## Acceptance and rollback

Use fictional Email and FileOS evidence only. Prove exact quote in its own
current body, cross-tenant/source denial, exclusion and stale-version hiding,
hidden-before-limit paging, hidden successor behavior, scope denial, malformed
Unicode/Markdown injection safety, deterministic bytes for a fixed snapshot,
output bounds, audit privacy and no source or KnowledgeCore mutation beyond
the fixed read-audit receipt. Run full local and hosted gates.
Rollback disables the new route and client operation; immutable facts and
evidence are retained. A future independently gated renderer may add other
sections only when each displayed line has an export-time citation contract.
