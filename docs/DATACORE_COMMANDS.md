# MasterBrain Shared Commands

The `masterbrain` command is the source-neutral operator surface. It currently offers
read-only DataCore and FileOS inventory commands. The legacy `email-brain` command
remains the Email capability surface. No shared command moves, renames, quarantines,
deletes or modifies a source file.

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
and the invariant `source_effects: false`. This is explicit one-snapshot operation,
not a watcher or automatic live-root enrollment.

## Donor parity

```sh
python scripts/datacore_parity.py --fos-repo ../FOS-Master --stress-files 3000
```

The harness refuses an unpinned donor unless explicitly overridden. It compares
fixture and scale scans for hash/name/both methods plus text/binary pair comparison,
SHA-256 and MD5. Normalization removes only temporary root paths and modification
timestamps; it does not ignore result counts, hashes, errors, grouping or sizes.
