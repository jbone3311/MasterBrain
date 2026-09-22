# MasterBrain Shared Commands

The `masterbrain` command is the source-neutral operator surface. It currently offers
read-only DataCore and FileOS inventory commands plus explicit private publication
commands. The legacy `email-brain` command remains the Email capability surface. No
shared command moves, renames, quarantines, deletes or modifies a source file or
mailbox.

## Bridge one current Email evidence version

```sh
MASTERBRAIN_DSN='postgresql://least-privileged-runtime/...' \
  masterbrain email bridge \
  --config /private/operator/email-bridge.json \
  --evidence-id b22f0f5c-a784-46a1-95a7-b2b96e1f8396 \
  --idempotency-key 93c5a004-81ab-45b6-8652-e8ced2b40e47 \
  --check
```

The owner-private closed config contains `version: 1`, absolute `credentials_file`
and `token_file` paths, and `code_revision`. Its expiring worker must have exactly
`brain.source.ingest` and `brain.document.publish`. `--check` authenticates and
validates the safe runtime database role without reading or writing the selected
evidence. Remove it only after preflight succeeds.

Normal execution maps only the named current, visible Email version into DataCore.
Reuse the exact key after an uncertain result; never reuse it for another evidence
version or code revision. Output contains opaque identities, chunk count and replay
state, never Email content, addresses or provider identifiers. The command does not
scan an account, contact a provider, modify a mailbox or redirect legacy Email search.

Preview one bounded page of eligible current versions in an explicit account:

```sh
MASTERBRAIN_DSN='postgresql://least-privileged-runtime/...' \
  masterbrain email bridge-plan \
  --config /private/operator/email-bridge.json \
  --account-id 392ef97f-305d-494a-aa2f-7cf29a7f16a3 \
  --limit 25 \
  --check
```

Normal execution returns only version UUIDs, recorded timestamps, already-bridged
labels and a next cursor. `--after` continues from a returned cursor. `--check` does
not inspect the account. The command is a read-only operator preview, not execution
authority; it creates no bridge, contacts no provider and authorizes no batch executor
or automatic backfill.

Preview the next dependency-safe attachment or approved-document page separately:

```sh
MASTERBRAIN_DSN='postgresql://least-privileged-runtime/...' \
  masterbrain email bridge-parts-plan \
  --config /private/operator/email-bridge.json \
  --account-id 392ef97f-305d-494a-aa2f-7cf29a7f16a3 \
  --kind attachment \
  --limit 25 \
  --check
```

Use `--kind document` for approved extractions whose current parent message and
attachment are already bridged. Normal output contains opaque legacy IDs, stable
timestamps, state and already-bridged labels only. `--after` continues only the
selected kind; `--check` does not inspect the account. This preview creates no batch
authority, bridge receipt, approval or provider/mailbox effect.

Execute one reviewed attachment or document plan only after checking it:

```sh
MASTERBRAIN_DSN='postgresql://least-privileged-runtime/...' \
  masterbrain email bridge-parts-batch \
  --config /private/operator/email-bridge.json \
  --plan /private/operator/email-attachment-batch.json \
  --check
```

The owner-private plan contains one account, one exact `attachment` or `document`
kind, the configured revision, 1–100 unique ordered target/key pairs and a canonical
digest covering all of them. Remove `--check` only after validation. Execution stops
at the first refused dependency; retry the exact unchanged plan so completed items
replay. It never mixes kinds, follows preview cursors, bridges missing dependencies,
contacts providers or changes a mailbox.

Execute one reviewed, sealed plan only after checking it:

```sh
MASTERBRAIN_DSN='postgresql://least-privileged-runtime/...' \
  masterbrain email bridge-batch \
  --config /private/operator/email-bridge.json \
  --plan /private/operator/email-batch.json \
  --check
```

The owner-private plan is closed and contains `version: 1`, one account UUID, the
config's exact `code_revision`, 1–100 unique ordered version/key pairs, and their
canonical `plan_sha256`. Remove `--check` only after validation. Execution stops on
the first refused item; retry the exact unchanged plan so completed items replay and
remaining items retain their original keys. The command never discovers or continues
preview pages, bridges attachments/documents, contacts providers or changes mailboxes.

## Bridge one Email attachment or approved PDF derivative

After the parent message bridge succeeds, the same private config can bridge one
explicit attachment occurrence:

```sh
MASTERBRAIN_DSN='postgresql://least-privileged-runtime/...' \
  masterbrain email bridge-attachment \
  --config /private/operator/email-bridge.json \
  --attachment-id 392ef97f-305d-494a-aa2f-7cf29a7f16a3 \
  --idempotency-key bb642bc3-a561-446d-8dc3-971d99fc9de9 \
  --check
```

After that occurrence bridge succeeds, one already-approved immutable PDF extraction
can be published onto the same shared evidence:

```sh
MASTERBRAIN_DSN='postgresql://least-privileged-runtime/...' \
  masterbrain email bridge-document \
  --config /private/operator/email-bridge.json \
  --extraction-id f678b2e7-f5f5-4ddd-a95f-41106160a598 \
  --idempotency-key fda0019c-354a-49e6-931e-42ffcc608ee7 \
  --check
```

Both commands use the exact scopes and preflight rules above. `--check` does not
inspect its target. Normal output contains opaque identities, bounded counts/status
and replay state only. Neither command enumerates Email, approves or processes a
document, reads attachment bytes or changes legacy search.

## Hash one file

```sh
masterbrain datacore hash /authorized/path/file.pdf
```

The default is SHA-256 and output is JSON. An unreadable file fails with a generic
message so sensitive paths or OS details are not copied into ordinary error output.

## Compare two files

```sh
masterbrain datacore compare first.txt second.txt
```

Returns donor-compatible digest, size, extension, name and—for supported text
extensions—content similarity. It is an observation only, never deletion authority.

## Find duplicates

```sh
masterbrain datacore duplicates /authorized/root --method hash
masterbrain datacore duplicates /authorized/root --method name
masterbrain datacore duplicates /authorized/root --method both
```

Optional bounds: `--min-file-size`, `--max-file-size-mb`, repeated
`--include-extension`, and repeated `--exclude`. Defaults preserve the extracted
FOS-Master contract, including component-aware junk/index/database exclusions.

## Create a FileOS snapshot

```sh
masterbrain fileos snapshot /authorized/root \
  --source-id files_primary \
  --output /private/operator/path/snapshot.json
```

The manifest contains stable opaque item/version IDs, relative locators, SHA-256,
size, media type, nanosecond modification time, scan policy, explicit error codes and
counts. It excludes the absolute root so a portable manifest does not disclose the
host path. It does not include file bytes or extracted text.

Snapshots skip symlinks by default. `--follow-file-symlinks` permits file symlinks
only when the resolved target stays inside the authorized root; directory symlinks and
root escapes remain excluded. Files that change during hashing are reported and not
published. Existing output is never replaced without `--force`; output publication is
an fsync plus atomic replace in the selected output directory.

For reproducible acceptance tests, `--observed-at` accepts an explicit timezone-aware
ISO timestamp. Normal operation records current UTC. Source IDs are lowercase stable
identifiers such as `files_primary`, not display paths or secrets.

## Publish an authorized snapshot

```sh
MASTERBRAIN_DSN='postgresql://least-privileged-runtime/...' \
  masterbrain fileos publish \
  --config /private/operator/fileos-primary.json \
  --idempotency-key 93c5a004-81ab-45b6-8652-e8ced2b40e47 \
  --check
```

Remove `--check` only after preflight succeeds. The private closed configuration binds
`source_id`, absolute `root`, `manifest_file`, `credentials_file`, `token_file` and
`code_revision`. It may additionally bind both `document_image_id` and
`docker_binary` to enable the isolated PDF/DOCX/XLSX worker. Configuration, credential,
token and manifest files must be owner-private, outside the source checkout, and must
not be passed through command arguments as secrets. The DSN is read only from
`MASTERBRAIN_DSN`.

The expiring credential must be a worker with exactly `brain.source.ingest` and
`brain.document.publish`. The UUID and exact manifest are reused for an uncertain
retry; never reuse the key for a different snapshot. Output is compact counts only,
including extraction outcomes, new/unchanged versions, published/changed documents,
an immutable completion ID/time/recorded flag, and the invariant
`source_effects: false`. Completion is recorded only after all items are accounted.
This is explicit one-snapshot operation, not a watcher or automatic live-root
enrollment.

## Build, activate or roll back a FileOS index generation

After a snapshot has a completed run receipt, validate a one-shot generation command:

```sh
MASTERBRAIN_DSN='postgresql://least-privileged-runtime/...' \
  masterbrain fileos index \
  --config /private/operator/fileos-primary-index.json \
  --run-id 93c5a004-81ab-45b6-8652-e8ced2b40e47 \
  --idempotency-key 29f84819-a8ce-4235-9910-54404f85f8c7 \
  --check
```

Remove `--check` to build an immutable generation for that exact latest completed run
and activate it. The private closed configuration binds `source_id`,
`credentials_file`, `token_file` and `code_revision`. Its worker must have exactly
`brain.document.publish` and `brain.index.activate`. A crash after generation readiness
but before activation is safe: reuse the exact run, code revision and activation key.

Rollback activates an existing ready generation without rebuilding it:

```sh
MASTERBRAIN_DSN='postgresql://least-privileged-runtime/...' \
  masterbrain fileos index \
  --config /private/operator/fileos-primary-rollback.json \
  --generation-id index_generation_opaque \
  --idempotency-key ad27bd64-313e-4b4a-8788-c7a3e782276c \
  --check
```

Activation-only credentials must have exactly `brain.index.activate`; their config may
omit `code_revision`. Use a fresh key for each new activation intent and reuse it only
for an uncertain retry of the same generation. Output contains opaque generation IDs,
counts, digests, receipt times and replay flags only. The command never scans or
changes source files and does not redirect existing global search.

## Donor parity

```sh
python scripts/datacore_parity.py --fos-repo ../FOS-Master --stress-files 3000
```

The harness refuses an unpinned donor unless explicitly overridden. It compares
fixture and scale scans for hash/name/both methods plus text/binary pair comparison,
SHA-256 and MD5. Normalization removes only temporary root paths and modification
timestamps; it does not ignore result counts, hashes, errors, grouping or sizes.
