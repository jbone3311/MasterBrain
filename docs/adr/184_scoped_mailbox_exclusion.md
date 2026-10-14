# ADR-184 — Pre-download mailbox exclusion for scoped Email

Status: accepted for a synthetic-only implementation. This does not authorize a
Fastmail connection, change an existing enrolled scope, or retire FileOS.

## Problem

An Email can belong to both the selected mailbox and a private mailbox. A
positive `Email/query` filter therefore does not prove that it is safe to
download. If a previously indexed Email later gains a private mailbox, simply
skipping it leaves old content searchable. Immutable evidence must remain
intact, so exclusion cannot be implemented as a purge or as a false provider
deletion.

## Decision

- The first policy is a bounded, exact set of excluded JMAP mailbox IDs on the
  already bounded `ScopedMailWindow`. It is checked against the complete
  `Email/get` membership map after independent mailbox/date scope validation,
  before blob download **or retained-byte lookup/reuse**. Invalid metadata
  fails the whole page closed. No sender matching, inferred labels or generic
  cross-source filter language is implied.
- The canonical, sorted exclusion set and policy version are included in the
  scoped fingerprint. The existing empty-set fingerprint remains unchanged
  for compatibility. Enrollment and worker lease already pin that fingerprint;
  a changed policy cannot silently reuse an old cursor or live account.
- An excluded row produces an `exclude_message` event and `excluded` current
  sync status, with no raw bytes, MIME parsing, quarantine receipt, normalized
  document, attachment, content digest, or content-bearing telemetry. If an
  older projection exists, its current-search visibility is removed in the
  same page transaction, without deleting immutable historical evidence.
  Re-entry after removal of the excluded membership needs a fresh, ordinary
  metadata check and download before publication.
- The internal, tenant-isolated inventory and status ledger retains the opaque
  provider ID and a policy-bound event key. Exact reconciliation and hiding an
  already indexed message cannot be made reliable with literally *only* an
  aggregate count. Public/operator receipts expose counts, not those IDs or
  mailbox memberships. This is an explicit correction to issue #184's
  count-only wording, not permission to retain excluded content.
- FileOS continues to use its donor-derived path policy and exclusion ledger.
  Shared DataCore may standardize the outcome (`included`, `excluded`,
  `unknown`) but must not force JMAP mailbox semantics onto filesystem paths.

## Invariants and proof

Synthetic tests must prove mixed selected/private membership, malformed
membership, no blob or retained-byte lookup for excluded rows, no new content
records, existing Email and Brain current search suppression, re-entry after
membership removal, policy-bound cursor mismatch, complete inventory counts,
idempotent replay, tenant fences, and unchanged FileOS exclusion parity. A
policy does not retroactively purge retained evidence or add a new historical
read permission. Existing human evidence-read permissions can still retrieve
retained history; changing that access or retention requires a separate
reviewed ADR. Historical evidence remains privileged and audited.
Retained KnowledgeCore assertions are a separate visibility surface and are
not covered by this tranche; they require a transitive evidence-visibility
review before any real private-mail pilot. This is not a claim that every
historical or derived surface is suppressed.

Rollback stops the scoped worker and disconnects the disposable source. Do not
down-migrate, remove immutable events or unpin a used account. A new policy for
an already used account requires a separately reviewed transition; this ADR
does not authorize editing its fingerprint in place. All acceptance data is
fictional and disposable.
