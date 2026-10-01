# ADR-122 — Validate a FileOS completion ledger once per receipt

Status: accepted for the existing private v1 completion path.

## Context

Migration 0018 placed a deferred whole-run count/outcome check on both the
completion receipt and **each** run-item insert. One 3,000-item completion
therefore rescans the growing ledger 3,001 times at commit. In disposable
PostgreSQL 17.11 testing this made a legacy v1 stress fixture spend tens of
seconds committing and sometimes consume the later review query's five-second
statement budget under full-suite load (issue #71). The receipt must still
reject missing, extra, late or misclassified rows, including direct SQL writes.

## Decision

- Make the run-item-to-receipt foreign key deferred so new items can be inserted
  **before** their receipt in one transaction. The private completion writer
  follows that order. Existing exact replay checks the saved rows without
  inserting them again.
- Retain the deferred whole-ledger trigger on the receipt. At commit it compares
  the final run-item count and outcome map once. Do not weaken its validation.
- Replace the per-item deferred whole-ledger trigger with an immediate guard.
  Before each run-item insert it takes the existing per-source advisory lock
  and refuses any already-inserted receipt for that run identity. A committed
  receipt cannot gain a late item. A receipt-insert trigger takes the **same**
  lock, so even a direct SQL receipt writer cannot race with another item
  writer through an uncommitted receipt. The deferred foreign key
  prevents orphan items from committing.
- Keep receipt and item immutability, forced RLS, tenant-login fences, audit,
  absence semantics and public API unchanged. This is a forward migration;
  historical receipts and applied migration checksums are not rewritten.

## Verification and rollback

Test the exact private completion and replay, missing/extra/wrong-outcome
direct SQL, late insert, concurrent insert, tenant isolation, migration of a
populated database, and a 3,000-item completion benchmark. The new path must
preserve every existing integrity refusal and materially reduce commit work.
Run full CI, strict runtime and populated restore before merging. Rollback is
forward-only: stop the writer and deploy a later migration if required; never
drop completed evidence or receipts.
