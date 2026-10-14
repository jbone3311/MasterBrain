# ADR-189 — Private current-FileOS statement replay receipt

Status: accepted for synthetic/disposable testing only. This does not approve a
live FileOS root, a verified investment, an Email/PDF/OCR derivation, or donor
cutover. ADR-188 supplies the exact bounded text transform being replayed.

## Context

ADR-172/173's statement proposal and preview bind internally consistent source
and text hashes, but the original bytes may have produced unrelated text. A
pure ADR-188 replay result is not durable, source-authorized, or tied to one
proposal. The next step must use the existing confined FileOS source reader,
not a caller-provided byte string or an API process filesystem read.

## Decision

- Add a private worker library operation requiring `brain.document.publish` and
  a worker identity. It takes one opaque proposal ID and an explicit authorized
  FileOS root. A first tenant transaction checks the caller's source allowlist,
  exact proposal/document/evidence/version/item/source identities, active and
  still-current FileOS source, bounded size, `fileos-text-v1` normalizer, and
  stored physical-root binding. Outside the transaction, the no-follow bounded
  reader reacquires the exact locator. A second tenant transaction rechecks
  the entire basis while holding source/item share locks before insertion;
  filesystem I/O never holds those database locks.
- Replay the transform from the opened bytes through ADR-188, requiring exact
  source size/SHA and normalized text/SHA. Recheck root binding after the read.
  Any missing, changed, oversized, unsupported or ambiguous input fails closed
  with no receipt. The worker never accepts arbitrary source bytes, stores no
  file path, bytes or quote in the receipt, and emits only opaque audit IDs.
- Append one tenant-fenced immutable replay receipt per proposal. Its identity,
  source/text digests, source size, normalizer and root binding are checked on
  exact replay; a conflicting replay fails. Composite foreign keys, forced RLS,
  tenant-login fence, append-only and protected-TRUNCATE guards apply. SQL
  rejects a receipt whose stored basis does not match the current proposal,
  document and FileOS source.
- This is a *worker-observed replay receipt*, not a cryptographic attestation
  against a compromised runtime SQL login. That login can still insert a
  same-basis row; issue #7's database trust boundary remains. The public owner
  preview remains `proposed_extraction` and does not expose a new verified flag
  or promote a financial claim. No older proposal is upgraded merely because
  its hashes agree; it needs a fresh authorized byte replay.

## Verification and rollback

Disposable fictional PostgreSQL tests must cover exact replay, unrelated text
despite valid hashes, changed bytes/root, stale version, source-grant and
cross-tenant refusal, replay/concurrency, direct-SQL mismatched basis and
mutation/TRUNCATE denial, and absence of reviewed assertions. Full CI,
strict-runtime and populated restore remain required. Rollback disables this
private worker operation and retains historical receipts for audit; no source
or proposal is deleted or changed.
