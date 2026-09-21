# ADR-029 — Isolated large-MIME recovery

Accepted for explicit synthetic/local-worker and CI use, 2026-09-20. Builds on
ADR-027/028 without granting mailbox writes, raw downloads or binary execution.

## Decision

Add a dedicated MIME worker that reads at most 16 MiB from stdin, normalizes body
text and accounts for attachments using existing deterministic rules. Existing
in-process API/ingestion parsing remains capped at 1 MiB. PDFs, Office, images,
archives and active payloads remain deferred/skipped, not executed or malware-scanned.
Bound output to 8 MiB and validate a strict versioned schema, raw hash, field/part
budgets, statuses and Unicode before publication. Retain original encrypted bytes.

An explicit trusted operator/worker can inject the sandbox processor into the
existing human-authorized Recovery library. Its parser version includes the exact
local image ID. Recovery publishes a new immutable evidence version under that
identity, retaining source hashes, events, cursor, current-event fencing and audit.
Default API/UI retry stays on the existing parser; it cannot select an image or
launch Docker. A future authenticated job queue/control integration is required
before exposing large-message recovery through the hosted interface.

The runner uses a caller-approved local image ID (never tag/pull), a fixed local
Docker UNIX socket, no network, read-only root, no mounts, unprivileged UID, dropped
capabilities, no-new-privileges, default seccomp, bounded memory/CPU/PIDs and wall
time, disabled Docker logs and scrubbed stderr. Raw bytes travel in pipes, never
command arguments or host temporary files. Stdout is concurrently drained with a
hard byte limit. Timeout/crash/malformed output is infrastructure failure: no
cached parsing rejection or partial projection. Deterministic MIME rejection alone
may create an immutable failed attempt. Exact-owned container cleanup is verified.

The Docker controller is privileged infrastructure, not a public API dependency.
Never mount the daemon socket into the Email Brain API or untrusted parser, and
never give the parser database credentials, object keys or provider tokens.
Container isolation is defense in depth, not a claim of invulnerability to kernel
exploits. Cloud isolation/runtime acceptance remains a separate deployment gate.

## Tests and rollback

Test oversized/malformed/hostile MIME, binary deferral, bounded JSON validation,
hash mismatches, subprocess timeout/output flooding, fixed launch controls and
ownership-checked cleanup. CI must run a real restricted container against synthetic
attachment-heavy mail, then prove encrypted retained evidence -> isolated parser ->
PostgreSQL recovery -> searchable cited text, with RLS and crash/stale-event tests.
Offline mocks cannot substitute for that executable container proof.

No new SQL schema is required: migration 0008 already supports parser-versioned
evidence; 0009 retains external raw bytes. Disable the optional processor to stop
new processing; keep existing evidence/readers. Never rewrite source bytes, delete
attempts or roll back provenance. CPU/resource limit changes require a new worker
contract/image and review.

Sources: [Docker run controls](https://docs.docker.com/reference/cli/docker/container/run/),
[no network](https://docs.docker.com/engine/network/drivers/none/),
[logging drivers](https://docs.docker.com/engine/logging/configure/),
[daemon privilege boundary](https://docs.docker.com/engine/security/).
