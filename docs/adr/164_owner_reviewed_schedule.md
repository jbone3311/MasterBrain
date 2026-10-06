# ADR-164 — Explicit reviewed schedule in the owner workspace

Status: merged through PR #159 after exact-head full CI, strict-runtime and
restore passed; merged-main gates remain open. This grants no hosted,
live-source or action acceptance.

## Context

ADR-160 and ADR-161 merged source-aware, paged event-occurrence and
commitment-due reads. The provider-neutral client can use them, but `/brain`
cannot yet show either chronological view. Lexical Ask and Search do not
substitute for an explicit date-window read and must not imply that an undated
or hidden reviewed assertion was searched.

## Decision

- Add a separate, explicit **Reviewed schedule** panel to the read-only owner
  workspace. Require the owner to select valid UTC start and exclusive end
  dates, with a positive window of at most 366 days. Offer separate **Events**
  and **Commitments due** controls only under All-sources focus. Do not route
  free-text questions automatically, fetch on page load or change source
  grants. Use the existing `knowledge.search` routes with fixed 10-item pages,
  default `unsuperseded` visibility and no implicit project/state filter.
- Validate each complete response before rendering: route-specific coverage,
  exact limit/visibility/filter, bounded unique ordered rows, time window,
  typed identities and direct evidence links, recorded cutoff and exact next
  cursor. Show one page at a time, with an explicit Next control that carries
  the server cutoff and cursor. A later page is a recorded-time continuation,
  not a durable snapshot. Undated rows are excluded; source freshness and
  real-world truth are not established. Display every untrusted title,
  description and error inertly; evidence expansion keeps its separate grant.
- Reuse the same in-memory credential, no-cookie/no-store same-origin request
  boundary. Editing dates or changing token/focus/session aborts or invalidates
  an in-flight schedule read and clears its prior page. Denied, malformed and
  hidden-cursor responses fail visibly without partial rendering or fallback.
  The controls perform no proposal, execute or source effect.

## Verification and rollback

Browser tests cover no automatic fetch, exact UTC window, 366-day refusal,
All-focus gating, both route shapes, paging/cutoff, inert hostile text,
independent evidence access, invalid/order/cursor refusal, denial and stale
response clearing. Existing PostgreSQL API/client tests remain the server
authority. Run full Python/browser, docs, strict-runtime and restore gates
on the exact branch before merge. Rollback removes only the first-party
controls and renderer; ADR-160/161 APIs and immutable knowledge remain.
