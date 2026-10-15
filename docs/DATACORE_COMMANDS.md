# MasterBrain Shared Commands

The `masterbrain` command is the source-neutral operator surface. It currently offers
read-only DataCore and FileOS inventory commands plus explicit private publication
commands. The legacy `email-brain` command remains the Email capability surface. No
shared command moves, renames, quarantines, deletes or modifies a source file or
mailbox.

ADR-218 adds an **internal** shared DataCore confined FileOS text replay used
by statement proposals and human source-tier reviews. It re-reads only one
already-authorized current source, verifies source bytes and the complete
normalized text, and records a point-in-time immutable receipt. There is no
public `masterbrain` subcommand or unattended live-root executor for this yet;
the tested operation is `SourceTierFileOSReplayStore.record_current_text_replay`
inside a scoped worker. PDF/OCR/spreadsheet completeness and Email-byte replay
remain separate gates.

Every database-backed private `masterbrain` command below accepts
`--tenant-bound-db` on both `--check` and execution (ADRs 135, 138 and 139).
With this opt-in, `MASTERBRAIN_DSN` must be a DBA-enrolled login bound to the
authenticated worker's exact tenant; shared, owner and wrong-tenant logins
fail before check mode succeeds. Keep the DSN out of arguments, plans and
source content. This is synthetic/disposable containment, not hosted
credential management or acceptance. ADR-141 separately adds the same named
opt-in to the three `email-brain` worker commands; other legacy commands are
not covered. See [tenant-login contract](TENANT_LOGIN_FENCE.md).

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

For a synthetic tenant-bound database login (ADR-135), pass
`--tenant-bound-db` to both check and execution. The command then requires
`MASTERBRAIN_DSN` to be a DBA-enrolled login bound to the authenticated worker's
exact tenant; a shared, unbound or wrong-tenant login fails before intake. Do
not put a DSN on the command line or fall back to the legacy shared login for
hosted use. ADR-138 also permits this option on `fileos index`, and ADR-139
extends it to the Email bridge and archive derivative commands; none of these
is a hosted release claim.

The expiring credential must be a worker with exactly `brain.source.ingest` and
`brain.document.publish`. The UUID and exact manifest are reused for an uncertain
retry; never reuse the key for a different snapshot. Output is compact counts only,
including extraction outcomes, new/unchanged versions, published/changed documents,
an immutable completion ID/time/recorded flag, and the invariant
`source_effects: false`. Completion is recorded only after all items are accounted.
This is explicit one-snapshot operation, not a watcher or automatic live-root
enrollment.

## Publish one selected archive text member

After a source snapshot and its isolated archive inventory have been persisted, preview
one bounded page of eligible members without reading the archive:

```sh
MASTERBRAIN_DSN='postgresql://least-privileged-runtime/...' \
  masterbrain fileos archive-text-plan \
  --config /private/operator/archive-member.json \
  --inventory-id archive_inventory_0123456789abcdef0123456789abcdef \
  --limit 25 \
  --check
```

Remove `--check` to run the read-only preview. `--after` accepts only a returned sealed
member ordinal. Output contains eligible text-member virtual locators, bounded metadata
and already-published labels; treat it as private untrusted source metadata. The preview
does not construct Docker, read archive bytes, generate keys, write derivatives or
authorize a batch. Parent replacement makes the inventory unavailable.

After reviewing one returned member, validate the private one-member command:

```sh
MASTERBRAIN_DSN='postgresql://least-privileged-runtime/...' \
  masterbrain fileos archive-text \
  --config /private/operator/archive-member.json \
  --inventory-id archive_inventory_0123456789abcdef0123456789abcdef \
  --member-locator reports/summary.md \
  --idempotency-key 93c5a004-81ab-45b6-8652-e8ced2b40e47 \
  --check
```

The closed version-1 config binds the absolute authorized FileOS root, immutable
`sha256:` archive worker image, absolute Docker binary, private credential/token files
and deployed code revision. Its expiring worker has exactly `brain.source.ingest` and
`brain.document.publish`. `--check` validates configuration, authentication and the
least-privileged database role without querying the inventory, invoking Docker,
reading the source or consuming the key.

Remove `--check` only for the exact reviewed inventory/member pair. The source archive
must still be current and byte-identical before and after the fixed restricted worker
read. Eligible bounded text is published as one deterministic derivative with parent
archive and inventory provenance. Reuse the exact key only after an uncertain result.
Output is content-free: opaque IDs, chunk count, replay state and
`source_effects: false`; it never includes the locator, path, bytes or normalized text.
There is no enumeration, glob, batch, automatic sibling continuation, public route or
current-search activation.

## Publish one selected archive PDF or Office member

After a current archive inventory identifies an exact `.pdf`, `.docx` or `.xlsx`
member, validate the private two-worker command:

```sh
MASTERBRAIN_DSN='postgresql://least-privileged-runtime/...' \
  masterbrain fileos archive-document \
  --config /private/operator/archive-member.json \
  --inventory-id archive_inventory_0123456789abcdef0123456789abcdef \
  --member-locator reports/approved-report.pdf \
  --idempotency-key fda0019c-354a-49e6-931e-42ffcc608ee7 \
  --check
```

The same closed version-1 archive config must also bind `document_image_id` to an
immutable `sha256:` image. `--check` validates private configuration, authentication
and the least-privileged database role without selecting the member, constructing
either worker, reading bytes or consuming the key.

Remove `--check` only for the exact reviewed inventory/member pair. The archive-member
worker verifies and releases only that member in memory; the separate document worker
then applies the existing bounded PDF/DOCX/XLSX contract. Publication rechecks the
current parent, sealed inventory/member and exact processor/revision inside the
transaction. Reuse the exact key only for an uncertain retry.

Output contains opaque identities, format, bounded metadata counts, chunks, replay
state and `source_effects: false`. It never includes locator, path, bytes, text,
document properties, worker details or underlying faults. Raw member bytes are never
persisted. The derivative is retained-history-only: this command grants no current
search, preview, batch, recursion, automatic sibling continuation, scheduler, public
route or source effect.

## Publish one selected archive image OCR member

Checkpoint 5C implements the accepted private command. Hosted
[CI 35836198307](https://github.com/jbone3311/MasterBrain/actions/runs/35836198307)
and [restore 35836198414](https://github.com/jbone3311/MasterBrain/actions/runs/35836198414)
are green. For one current image member already named by its inventory
and virtual locator, run:

```sh
MASTERBRAIN_DSN='postgresql://least-privileged-runtime/...' \
  masterbrain fileos archive-image \
  --config /private/operator/archive-member.json \
  --inventory-id archive_inventory_0123456789abcdef0123456789abcdef \
  --member-locator images/receipt.png \
  --idempotency-key 93c5a004-81ab-45b6-8652-e8ced2b40e47 \
  --check
```

The same closed version-1 archive config must additionally bind a separate immutable
`image_ocr_image_id` digest. Check mode validates the private configuration, exact
worker identity and database role without selecting a member, constructing either
worker, reading source bytes or consuming the key. Remove `--check` only for the
explicit reviewed selection. The archive reader releases one hash-bound member in
memory; the separate image worker fully decodes and OCRs it. Only complete nonempty
text is published through the current-parent/member and idempotency fences.

Output is limited to opaque identities, chunk count, replay state and false source
effects. Empty, deferred, failed, unsupported or stale selections receive a generic
refusal without a partial derivative. Reuse the exact key after an uncertain result.
No path, locator, OCR text, image dimensions, EXIF, bytes, worker fault or credential
is returned. See the [operator contract](ARCHIVE_MEMBER_IMAGE_OPERATOR.md).

## Execute a sealed archive-member text batch

After reviewing a preview, create an owner-private plan containing one current
inventory ID, the configured code revision, 1–100 unique ordered member locators,
one caller-supplied UUID key per item, and the canonical `plan_sha256`. Validate it
without inspecting targets or constructing the worker:

```sh
MASTERBRAIN_DSN='postgresql://least-privileged-runtime/...' \
  masterbrain fileos archive-text-batch \
  --config /private/operator/archive-member.json \
  --plan /private/operator/archive-member-batch.json \
  --check
```

Remove `--check` only for the exact reviewed plan. Execution is sequential and stops
at the first refused target, stale parent, extraction failure or publication conflict.
Completed receipts remain valid; retry the exact unchanged plan so completed items
replay and remaining items keep their original keys. Output contains the plan digest,
counts and item indexes only—never locators, paths, bytes, normalized text or worker
details. The command never discovers members, follows preview cursors, skips failures,
runs items in parallel, changes source files or exposes a public route.

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
For a synthetic tenant-bound login, add `--tenant-bound-db` to both the check
and the actual command. The authenticated worker tenant must match the DBA-bound
`MASTERBRAIN_DSN`; a shared, owner or wrong-tenant login fails before indexing.

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
The same `--tenant-bound-db` option applies to this rollback mode. This is a
synthetic/disposable login fence, not hosted acceptance or FileOS cutover.

## Donor parity

```sh
python scripts/datacore_parity.py --fos-repo ../FOS-Master --stress-files 3000
```

The harness refuses an unpinned donor unless explicitly overridden. It compares
fixture and scale scans for hash/name/both methods plus text/binary pair comparison,
SHA-256 and MD5. Normalization removes only temporary root paths and modification
timestamps; it does not ignore result counts, hashes, errors, grouping or sizes.
