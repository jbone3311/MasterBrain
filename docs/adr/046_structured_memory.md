# ADR-046 — Reviewed structured memory and non-consuming changes

Accepted for the local prototype after the owner's request to build travel,
hotel and bill memory. No live mailbox, remote model or cloud enrollment follows.

## Decision

Add typed trip, flight reservation, hotel reservation and bill records. Store
immutable full revisions and source citations in PostgreSQL with forced tenant
RLS and account-bound foreign keys. A human owner with review/evidence scopes
must explicitly publish each version. Assistant evidence readers can read bounded
state and changes but cannot publish. Existing proposal approval applies nothing.

The first extractor recognizes only a documented, explicitly labelled text
format and returns an untrusted candidate. It neither guesses absent information
nor changes state. This is not general airline parsing, model quality or automatic
mailbox interpretation. Human edits are attributed as owner-reviewed claims,
not independently verified airline/bank facts. Source quotes must occur verbatim
in a current normalized email; quotes are provenance, not semantic proof.

Full snapshots use optimistic expected revisions and actor-bound idempotency
receipts. Identical payload/source/link publications do not create a change.
Corrections, cancellations and reopened bills append revisions. No email deletion
means trip cancellation. Related reservations link explicitly to a same-account
trip; no automatic matching by confirmation code or fuzzy name. Cross-account
links and field-by-field multi-source claims remain future work.

Serialize memory publications with a tenant advisory transaction lock before
assigning revisions, so a reader cannot skip a lower revision committed later.
Change cursors are opaque revision UUIDs resolved under tenant authorization,
not timestamps or consumable flags. Each client saves its own cursor. Pagination
is a bounded live feed; no acknowledgement endpoint. Account-scoped feeds reject
foreign-account cursors. Stop returning data when the account is inactive.

Summary separates last recorded memory change from last observed successful sync
(`caught_up`) and always declares interpretation coverage partial/manual. Missing
timestamps mean unknown, never fresh. A fixed documented 15-minute sync-age signal
is diagnostic, not an airline status guarantee or a scheduling promise. New source
mail does not imply its meaning has been processed. No live airline/bank checks.

## Verification, operations and rollback

Test typed values, dates/currencies, abstention, quote grounding, current-source
binding, owner/assistant/scope/tenant boundaries, no-op and changed-key replay,
concurrent updates/feed ordering, history, source deletion and inactive accounts.
Add populated memory to the synthetic database restore fixture. Audit identifiers
and outcomes only. No payloads, confirmation codes or amounts in ordinary logs.

Migration 0014 is additive. Stop API writers, apply migrations and regrant the
three new append-only tables before deploying. No broad UPDATE/DELETE grants.
Rollback disables memory routes/UI together and retains tables/history; do not
down-migrate or erase evidence. Existing mail/search/reader continue independently.
