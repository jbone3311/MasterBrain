# ADR-028 — Encrypted out-of-database raw evidence

Accepted for explicit local/CI use, 2026-09-20. Advances EB-005 and removes the
small-mail-only preservation boundary without claiming binary extraction or Azure
deployment. PostgreSQL remains authoritative for ownership, manifests and state.

## Decision

Add an optional injected encrypted filesystem backend for raw MIME, with a hard
16 MiB per-message bound. The default remains the existing 1 MiB inline mode.
No automatic discovery of keys, storage directories or provider credentials.
The caller must use private device storage outside Git/Dropbox and provide a
tenant-bound keyring. Tests use ephemeral synthetic keys and private temp roots.
This backend is a local implementation of the object contract, not Azure Blob/KMS.

Use the maintained `cryptography` AES-GCM implementation, 256-bit keys and random
96-bit nonces. Canonical authenticated context binds format version, tenant,
account, key ID, plaintext hash and size. Encrypt before disk, verify ciphertext
hash and authenticated plaintext on reads, reject path/symlink substitutions,
and publish atomically without overwriting existing objects. Local OS permissions
are not a substitute for cloud IAM or protection from a fully compromised process.
Key rotation retains old read keys; key-loss recovery requires a separate key backup.

Newly archived bytes use an immutable PostgreSQL manifest in `raw_objects`;
legacy inline bytes stay unchanged. Authorize account/membership before writing
objects, then stage and verify objects outside the SQL transaction. Under the
existing account lock/worker fence, recheck authorization and commit manifests,
events, projections/quarantines and cursor atomically. A crash before SQL commit
can leave an encrypted unreferenced object, never a cursor pointing at unstored
bytes. Do not delete staged objects on rollback: another transaction may refer
to them. Object availability/durability across disk loss requires coordinated
backup; an external operator deleting files cannot be prevented by SQL.

Raw MIME above the current 1 MiB parser budget is durably held with fixed reason
`mime_too_large`, not parsed in the API process, not marked extracted, and not
allowed to stall healthy subsequent mail. Recovery can read/verify the object but
keeps it held until a separately bounded large-MIME/extraction path is implemented.
The prototype advertises held counts and exact reasons, not complete extraction.

Fastmail explicitly opts into a larger download limit; JSON/control responses
keep their old bound. Opted-in durable workers use one-message pages to preserve
the existing 16 MiB aggregate page budget. Other providers retain current limits.
No live provider contact, mailbox writes, model calls or paid resources are enabled.

## Verification and operations

Require synthetic tests for cryptographic integrity/context, permissions/symlinks,
atomic publication, key rotation, concurrent duplicate writes, missing/corrupt
objects, storage/SQL failures, tenant isolation, large-message quarantine and
subsequent healthy progress. Restore must include both database manifests and
encrypted object bytes with independently supplied keys; database-only restore
must fail verification when referenced objects are absent. No plaintext/key archives
are uploaded to GitHub. Add read-only orphan reporting; actual garbage collection
and retention/purge require a separate policy and approved maintenance path.

## Migration and rollback

Migration 0009 adds nullable blob manifests and permits exactly one of inline
bytes or a complete manifest. Existing inline rows and hashes are not rewritten.
Stop API/workers before migration and upgrade all binaries; pre-0009 recovery and
backup tools cannot interpret external manifests. Disable new imports to roll
back behavior; keep compatible readers, manifests, encrypted bytes and keys.
Do not down-migrate, silently inline private blobs, or delete evidence.

## References

- [Cryptography authenticated encryption](https://cryptography.io/en/latest/hazmat/primitives/aead/)
- [Azure client-side encryption considerations](https://learn.microsoft.com/en-us/azure/storage/blobs/client-side-encryption)
- [Hosting target and pending gates](../HOSTING_DECISION.md)
- [Prior recovery contract](../QUARANTINE_RECOVERY.md)
