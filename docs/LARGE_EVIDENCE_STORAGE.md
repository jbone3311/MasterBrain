# Encrypted large-email evidence

Next increment: an explicit trusted worker can use
[isolated MIME recovery](ISOLATED_MIME_RECOVERY.md) to recover searchable body and
safe text attachments up to the 16 MiB retained-message limit. Default ingestion
and UI retry still use the 1 MiB parser; binary extraction remains deferred.

Implemented as an explicitly injected local/CI library, not a hosted service or
automatically enabled CLI option. See [ADR-028](adr/028_encrypted_large_evidence.md).

## Bounds and configuration

| Layer | Default | Explicit encrypted mode |
|---|---|---|
| Store raw MIME | 1 MiB inline PostgreSQL | 16 MiB encrypted filesystem objects |
| Fastmail blob download | 1 MiB | Caller sets `max_raw_bytes`, at most 16 MiB |
| Fastmail control JSON | 1 MiB; split oversized metadata batches | Unchanged |
| Worker listing page | ≤50 IDs, split by bytes/time | ≤50 IDs, split by bytes/time |
| Worker change page | 16 IDs | 1 ID |
| Aggregate ingestion bytes | 16 MiB | 16 MiB |
| MIME parser | 1 MiB | Unchanged; larger mail is held |

The caller constructs `EncryptedBlobStore(root, keys, active_keys)` and injects it
with `Store(dsn, blobs=backend)`. Keys map `(tenant UUID, key ID)` to 32 random bytes;
active keys map tenant UUID to key ID. Keep keys outside the database and object
backup. Retain previous key IDs for reads after rotation; existing evidence is not
silently re-encrypted. No credentials or keys are discovered automatically.

Use an absolute, private device path outside Git and Dropbox. Its parent must
already exist. The backend requires current-user-owned 0700 directories and 0600
regular files and rejects symlink traversal. Location outside Git/Dropbox remains
an operator responsibility, not an inferred filesystem rule. A fully compromised
process/current-user account is outside this boundary.

Configure the Fastmail client's download limit separately. A larger Store does
not silently permit larger provider downloads. Gmail, Graph and IMAP keep their
current limits. No real provider is contacted by installation or these tests.

## Publication and integrity

Account authorization precedes object writes. AES-256-GCM encryption occurs before
disk; authenticated context binds version, tenant, account, key ID, plaintext hash
and length. Private ciphertext temporary files are fsynced and published with
no-overwrite semantics. Duplicate/concurrent writes verify and reuse the object.
Reads validate manifest, ciphertext hash, authentication tag, raw length and hash.
The implementation reuses [cryptography AESGCM](https://cryptography.io/en/latest/hazmat/primitives/aead/).

Object staging is outside SQL transactions. Final ingestion rechecks membership,
account, cursor and worker fence under the account lock, then atomically commits
manifest, provider event, projection/quarantine and cursor. Failed SQL can leave an
encrypted unreferenced object; deleting it automatically could remove another
transaction's evidence. No garbage collector or deletion API is introduced.

All newly stored bytes use external encryption when configured. Existing inline
rows stay unchanged. Normalized text, metadata and legacy inline raw mail remain
in PostgreSQL: this feature does **not** encrypt the whole database.

## Held mail and recovery

Above the parser's 1 MiB budget, the complete message is preserved with fixed
`mime_too_large` quarantine reason. Subsequent healthy messages can progress; large
mail is not claimed parsed, indexed or malware-scanned. Retry returns 409 while
the parser budget is insufficient, without creating a cached failed attempt.
Missing keys/backend/files or corrupt encrypted evidence yield scrubbed API 503
`evidence_storage_unavailable`; recovery can retry after storage is restored.
The worker records bounded `retry` for storage failures without advancing cursor.

A message larger than the configured storage budget itself (1 MiB inline, up to
16 MiB encrypted) is not downloaded. It is held as a `source_too_large` receipt
with its provider metadata and reported size but no retained bytes (migration
**0052**), the cursor advances and the account is not paused. Retry and isolated
recovery return 409 for such a receipt; a larger budget applies at the next full
listing. A valid 50-ID metadata response over the separate 1 MiB control cap is
split by ID; a single row that still exceeds it does not advance the cursor.
See [ADR-110](adr/110_fastmail_sync_resilience.md).

## Backup, inventory and rollback

Back up the SQL database **and** encrypted object tree, with separately recoverable
keys. The [synthetic restore drill](RESTORE_DRILL.md) copies ciphertext, restores
SQL, rejects database-only/missing-object recovery, then checks decrypted raw hashes.
It does not prove cloud PITR, offsite durability, KMS or key-loss recovery.

`Store.object_inventory(ctx, account)` requires owner/evidence authorization and
reports referenced/present counts plus missing/unreferenced keys. It is bounded to
10,000 inventory entries and explicitly **not a consistent snapshot or deletion
authorization**. It checks names, not every object's ciphertext; use verified
reads/restore for integrity. Never log raw keys, mail or filesystem exceptions.

Stop old API/workers before migration **0009**; upgrade backup/recovery readers too.
The manifest has exactly five typed fields, contextual path/hash checks and exactly
one storage representation. Existing RLS and immutable-row protections remain.
Rollback means stopping new imports and keeping compatible readers, SQL, objects
and keys; never down-migrate or delete retained evidence.

Still required: Azure Blob/KMS adapter, independent key-backup drills, production
IAM/identity, authorized queued MIME processing, binary extraction/scanning, authorized
retention/purge, real-mailbox acceptance and load/soak testing.
