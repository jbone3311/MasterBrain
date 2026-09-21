# Isolated recovery of attachment-heavy MIME

This increment adds an explicit **trusted operator/worker library**, not a public
Docker endpoint or automatically running extractor. See
[ADR-029](adr/029_isolated_large_mime_recovery.md).

## What it does

The default ingestion parser still accepts at most 1 MiB. With encrypted storage,
larger messages up to 16 MiB are retained as `mime_too_large`. An authorized human
recovery executed by a trusted worker can now send those retained bytes to a
restricted MIME container, recover the bounded body/plain/calendar text and publish
searchable, versioned evidence. Source bytes, provider events and sync cursor remain
unchanged. Binary attachment receipts remain deferred/skipped, **not** successfully
extracted or scanned. A recovered message can still have incomplete attachments.

The operator constructs `DockerMimeProcessor(image_id)` using an already built,
approved local `sha256:` image ID, then `Recovery(store, processor=processor)`.
The call to `retry` must carry a human principal, both review/evidence scopes,
current owner membership, the current receipt and exactly `processor.parser_version`.
That version binds the worker contract to the full image hash. No tags, pulls,
arbitrary commands, model calls or source-provided configuration are accepted.

The existing HTTP/UI retry continues to use its ordinary bounded parser and cannot
select an image or launch this worker. Hosted integration needs an authenticated,
scoped job channel; do not shortcut that by giving the API access to Docker.

## Isolation and disclosure boundary

The controller uses the local Docker UNIX socket. **Daemon access is privileged**:
keep it on a separate trusted worker/controller host, never mounted inside the
public API or MIME container. The parser receives only raw message bytes through
stdin. No tenant keys, database/provider tokens, host volumes, sockets or inherited
host environment are disclosed to it. Approved images must contain no secrets.

Launch controls require no external network, read-only filesystem, unprivileged
UID, dropped capabilities, no-new-privileges, default seccomp, 512 MiB memory,
bounded CPU/processes and a 30-second parent wall deadline. The child sets Linux
resource limits, including 10 CPU seconds, before reading MIME. Docker logs are
disabled; stderr is discarded and raw input never enters command arguments or
host temporary files. Stdout is concurrently drained and capped at 8 MiB.

The parent validates a strict closed response envelope, contract and raw hash,
field/part/text budgets, valid Unicode and attachment outcomes before SQL. These
controls reduce risk; they are not proof against all parser/kernel vulnerabilities.
The process is still using the existing standard-library MIME parser, not a malware
scanner or a general document sandbox approved for arbitrary binary execution.

Sources: [Docker run](https://docs.docker.com/reference/cli/docker/container/run/),
[network isolation](https://docs.docker.com/engine/network/drivers/none/),
[logging](https://docs.docker.com/engine/logging/configure/),
[Docker security](https://docs.docker.com/engine/security/).

## Failure and publication

Only deterministic MIME rejection creates a cached `mime_rejected` attempt for the
image-bound parser version. A timeout, crash, resource failure, missing image,
malformed/oversized output, changed processor configuration or failed cleanup is
unavailability: no attempt or projection is cached. Existing quarantine remains.
Errors contain no mail, paths or subprocess output. Do not fix an error by raising
resource limits or changing image identity silently.

Publication retains the existing account lock and current-event check. Revocation,
provider deletion or newer mail while parsing prevents stale publication. Repeated
successful retries return the historical attempt without running another container.
The controller removes only its exact verified, ownership-labelled container; it
never prunes or removes unrelated containers. Interrupted controller/host cleanup
still requires operator supervision on a long-lived host.

## Verification and rollout

Ordinary tests exercise strict decoding, limits, parent process controls and recovery
fences with synthetic data. `tests/container_mime_checks.py` is an **explicit post-build
CI suite**: it runs the actual restricted image and proves encrypted raw evidence ->
container -> real PostgreSQL recovery -> body/attachment search and stable citations.
It is not silently skipped as part of normal test discovery. Run it explicitly with
the local image ID and a disposable `email_brain_test*` database, as CI does.
See [build receipt](BUILD_RECEIPT.md) for exactly which commit has been verified.

No SQL migration is needed beyond 0008/0009. Rollback disables new isolated recovery
while keeping readers and existing image-bound evidence. Still required: hosted job
authorization/queue, scanning and isolated PDF/Office/OCR/archive extraction,
production image signing/advisory gates, real-mailbox acceptance and long-running
resource/escape testing. No real mailbox or paid hosting is activated by this work.
