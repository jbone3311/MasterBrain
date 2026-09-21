# ADR-038 — Owner PDF approval, history and cited evidence

Accepted 2026-09-21 for the synthetic local prototype. No new mailbox, model,
worker, cloud, scanner or live-account permission.

## Decision

Build the owner experience over ADR-035/036's existing document APIs and separate
operator command. A search result's immutable message evidence exposes attachment
receipts. The owner explicitly selects one eligible PDF, loads its account's
configured processor/policy and history, then separately approves that exact
receipt. Merely searching, selecting or refreshing performs no approval/execution.

Use a separate static `document_review.js` asset for document controls and the
search/evidence screen, reusing the current authenticated request/text-only DOM
helpers. Serve only that fixed asset under the existing no-store/self-only policy.
Keep the existing MIME recovery screen, its configuration, queue and worker scopes
independent. No API data schema or migration is required.

## Safety and consistency

- Fixed synthetic-unscanned policy, exact image-bound PDF processor and account/
  receipt/source identity are shown before a one-hour approval. Server authorization
  and source fences remain authoritative; a displayed historical receipt may be
  rejected as no longer eligible.
- Validate closed job/capability/history/result envelopes and their expected
  identities before rendering controls. Page evidence is bounded text, never PDF,
  HTML, remote imagery or an executable citation. Explicit partial/deferred/failed
  outcomes and unscanned status remain visible.
- Separate session, search, document-view, selection and card generations prevent
  late responses or detached controls from acting after context changes. Clear
  private UI state on credential/account changes; a newer query supersedes older
  results. Do not fetch with newly entered credentials from an old callback.
- Generate one UUID idempotency key per exact account/receipt/processor/policy
  intent. An uncertain response retains the key across same-account refresh and
  reselection in the current session; retry only on an explicit click. Closing the
  page clears memory, not server grants; history is the reconciliation path.
- History pages replace rather than accumulate (at most 50). Refresh/cancel is
  explicit; no background polling. Cancellation may race completion; display the
  validated terminal server outcome, not an optimistic cancellation claim.
- Document search is off by default and independent of ordinary attachment search.
  A document hit uses its document ID/citation and page endpoint. Original message
  evidence remains available independently. No approval is implied by a search.

## Verification, operations and rollback

Add Node DOM contracts for the full flow, source/identity rejection, same-key retry,
double-click/race handling, account/session/query invalidation, bounded paging,
malformed output and text-only rendering. Re-run existing MIME/session suites.
Add static-asset/HTML tests; retain real SQL/actual-container/restore acceptance of
the unchanged backend. Browser/accessibility and live use remain separate gates.

Existing server audit events cover document approval/status/cancel/evidence/search;
no content logging or browser storage is added. Document the owner steps and failure
semantics. To roll back the screen, deploy compatible older UI assets: saved grants
and results remain, so disable approvals, cancel unfinished work or stop workers
separately if processing must stop. No database downgrade or source deletion.
