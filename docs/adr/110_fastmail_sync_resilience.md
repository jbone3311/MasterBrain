# ADR-110 — Fastmail listing, oversized mail and blob reuse

Status: accepted for the synthetic Email read worker, 2026-09-28. This changes how
the existing read-only Fastmail worker pages and accounts for mail; it grants no
mailbox write, enrollment, scheduler or live-source acceptance.

## Problem

Four behaviors of the worker would stop a real mailbox within hours of enrollment:

1. A message whose raw size exceeded the configured storage budget raised a
   protocol error, which paused the account. Nothing clears `paused`, so one
   ordinary attachment email halted synchronization until an operator edited
   the database. The `mime_too_large` path only covered mail that fit the download
   budget but not the parser budget.
2. Listing used positional `Email/query` pages of eight IDs (one with encrypted
   storage) and restarted from position zero whenever `queryState` or `total`
   changed. A mailbox receiving mail during backfill could never finish listing.
3. Every `Email/changes` update re-downloaded and re-parsed the full message even
   when only keywords or mailbox membership changed.
4. A `Retry-After` header containing a non-ASCII digit raised `ValueError` and
   paused the account; a lost worker lease escaped as an uncaught conflict.

## Decision

**Anchored listing.** Listing pages request an explicit ascending `receivedAt`
sort and page by `anchor`/`anchorOffset` from the last committed ID (RFC 8620
section 5.5). Creations and deletions elsewhere in the mailbox no longer shift the
worker's position; a deleted anchor (`anchorNotFound`) restarts the inventory
generation while preserving the original Email baseline. The provider total is
advisory: the inventory seal is the worker's own durable count of listed IDs, and
mail that changed during listing is replayed from the baseline. Checkpoint schema
version 3 records `anchor` and `listed`; a stored version 2 listing checkpoint is
relisted with anchors. Reconcile and changes checkpoints are unchanged.

**Bounded, partial listing pages.** A listing page asks for up to 50 IDs, then
commits a prefix once the 16 MiB page budget or a 40-second fetch budget would be
exceeded, using the JMAP `size` property to plan downloads. Change pages cannot be
split, so `maxChanges` is the largest count whose worst case fits the byte budget
(16 for the 1 MiB store, 1 for the 16 MiB encrypted store).

**Held oversized mail.** A message whose reported or streamed size exceeds the
store's raw budget is recorded as a `source_too_large` quarantine receipt with no
retained bytes, its provider metadata and reported size. The cursor advances; the
account is not paused; sync status counts it as quarantined; the retry route and
isolated recovery jobs answer 409 because there is nothing to parse. The held
version digest includes the budget, so a later full listing under a larger budget
ingests the message. Migration 0038 makes `raw_sha256` nullable for exactly this
reason and forbids it for every other reason.

**Blob reuse.** The projection now records the provider blob identity. When an
update names the same blob and the reported size matches the retained bytes, the
worker reuses retained evidence instead of downloading; ingestion still verifies
the digest against retained storage. A changed blob, an unreadable retained object
or a size mismatch falls back to a download.

**Small fixes.** `Retry-After` accepts only ASCII delay-seconds; anything else is
ignored rather than raised. A replaced or expired lease returns `lease_lost`
without recording an outcome; the read command counts it and does not treat it as
an operator error.

## Alternatives rejected

- `Email/queryChanges` for listing: Fastmail supports it, but it needs a stable
  query state to start from and does not remove the need for a certified full
  inventory before absence inference.
- Downloading oversized mail into a separate store: adds retention scope without
  a decision on retention; the receipt preserves accountability without bytes.
- Pausing on a lost lease: the account belongs to another worker; pausing would
  stop both.

## Validation and rollback

Unit tests cover anchored paging, restart on a missing anchor, positional
checkpoint relisting, byte- and time-bounded partial pages, held mail with and
without a reported size, held-version dependence on the budget, blob reuse and
its fallbacks, non-ASCII `Retry-After`, and lease loss. PostgreSQL tests cover
mid-listing churn without restart, anchor deletion, an oversized message next to
healthy mail with no download and no pause, a misreported size, flag-only updates
without downloads, the 256-message mailbox with changed blob identities, held
receipts refusing retry, and the populated upgrade through migration 0038.

Rollback stops the worker and returns to the prior code. Version 3 checkpoints in
the listing phase are not readable by the prior worker; expire them to a fresh
baseline. Migration 0038 is additive and stays; held receipts remain valid
evidence of accounted, unretained mail. No provider, mailbox or FileOS behavior
changes.
