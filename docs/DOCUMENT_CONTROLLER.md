# Running explicitly approved PDF jobs

Updated 2026-09-21. [ADR-036](adr/036_document_operator_controller.md) adds a
bounded synthetic operator command over [ADR-035's document jobs](DOCUMENT_PROCESSING.md).
No live account, scanner, hosted service or automatic approval is enabled.

## Two separate commands

| Command | Work and credential | Configuration |
|---|---|---|
| `process-jobs` | Held-message MIME recovery; exactly `email.process` | Existing MIME configuration; no PDF selector |
| `process-documents` | Approved synthetic PDF attachments; exactly `email.document.process` | Required `job_kind: pdf-document` and fixed policy below |

Both require a worker identity, not the demo human token. Mixed/broader scopes,
wrong kinds and cross-channel configurations are rejected. Private-file, keyring,
runtime-role, stop and count semantics reuse the [MIME operator primitives](PROCESSING_CONTROLLER.md),
not MIME approvals or its processor interface. The API receives no Docker access.

## Prerequisites

- Disposable PostgreSQL migrated through 0012, with runtime grants and existing
  current owner membership for the approved human and separately authenticated worker.
- Active **unenrolled synthetic account**, with a `synthetic:` secret reference.
  Never change a real account's labels to bypass this boundary.
- Trusted Linux controller with the fixed local Docker socket and explicit binary,
  plus a prebuilt immutable PDF image. Follow the [PDF build/isolation contract](PDF_WORKER.md).
- An existing approval for the same account, receipt, processor/image and policy;
  the controller never creates one. Human approval still requires review/evidence scopes.
- Existing source objects and original tenant keys if evidence is external; inline
  SQL sources need neither. No storage root or credential is created by preflight.

All configuration/registry/token/key files must be in existing owner-only 0700
directories, mode 0600, outside Git/Dropbox. Absolute no-symlink paths, single-link
regular files, size bounds and duplicate-JSON-key rejection apply. A registry holds
the token digest, not the token. Runtime DSN comes only from `EMAIL_BRAIN_DSN`.
Keep SQL administrator credentials and actual secrets out of command arguments/logs.

## Configuration and use

Shape only; replace the fictional UUID/image/path values privately:

```json
{
  "version": 1,
  "job_kind": "pdf-document",
  "policy_version": "synthetic-unscanned-pdf-v1",
  "account_id": "00000000-0000-4000-8000-000000000001",
  "image_id": "sha256:<64 lowercase hexadecimal characters>",
  "docker_binary": "/usr/bin/docker",
  "credentials_file": "/srv/email-brain-private/pdf-credentials.json",
  "token_file": "/srv/email-brain-private/pdf-token.txt",
  "blob_root": "/srv/email-brain-private/objects",
  "keys_file": "/srv/email-brain-private/keys.json"
}
```

Omit both storage fields for inline-only evidence. The existing
[keyring shape](PROCESSING_CONTROLLER.md#configuration-contract) accepts historical
keys only for the worker's tenant; this reader selects no active encryption/write key.
Unknown fields, tags, shell commands, path expansion and a different policy are refused.

```sh
email-brain process-documents --config /srv/email-brain-private/pdf-controller.json --check
email-brain process-documents --config /srv/email-brain-private/pdf-controller.json
email-brain process-documents --config /srv/email-brain-private/pdf-controller.json --max-iterations 60 --idle-seconds 5
```

Check validates configuration/identity/current account and optional key/root shape;
it reports `claims: 0` and `execution_verified: false`. It does not inspect/launch
the image, decrypt every object or certify host isolation or worker liveness.
Default run polls once. Limits are 1–1,000 polls and 1–60 seconds between them.
Durable retry/lease/consent deadlines are enforced by database time, not this sleep.

To configure the existing loopback approval API, set the exact image-derived version:

```sh
email-brain serve --document-processor-version 'sandbox-pdf-v1-<64 lowercase image hash characters>'
```

Omission disables new document approvals. This flag declares an approved channel,
not an online worker, image pull or execution permission. The human must still
explicitly approve the exact source/processor/policy through the [document API](DOCUMENT_PROCESSING.md).
Owner-screen attachment selection/approval/search is still pending; the existing
screen and `process-jobs` remain MIME recovery only. Ordinary ingestion defers PDFs.

## Results, stop and recovery

Exit 0 prints only bounded `polls`, fixed state counts, `stopped` and
`mailbox_effects: false`. A `completed` job saved an extraction result; the result
may be partial, deferred or failed. Always inspect the document outcome and
`scanner_status: unscanned`. `no_result` is not proof of an empty queue. A different
image, a delayed retry or an active lease can leave work unclaimed.

Exit 1 suppresses sensitive exception details and can follow committed work;
inspect durable history before retrying. Credential files are reread per poll and
before/after extraction. Removed/expired credentials, broader scopes or tenant/actor
changes stop execution; rotation to the same identity/scope is accepted. Config and
object keys are fixed per invocation. File revocation is not atomic with SQL;
database ownership/account fences and job cancellation remain stronger controls.

SIGINT/SIGTERM stop new claims and allow bounded in-flight work/cleanup. They do not
cancel saved approval. After a hard kill, inspect only the exact owned container
and allow leases to expire; never prune unrelated containers or reset job attempts.
Cancel pending jobs explicitly, stop invocations and disable new approvals to
withdraw the channel. Retain evidence/results/audit/keys; no migration rollback.

Tests cover private configuration, cross-channel authority, preflight, bounds,
identity rotation/revocation, source preservation, cancellation and restart. The
explicit container suite invokes fresh CLI processes through encrypted source,
actual restricted PDF, PostgreSQL and cited search. Exact passed revisions belong
in [BUILD_RECEIPT.md](BUILD_RECEIPT.md), not inferred from this guide.
Hosted supervision, service identity, scanner/live policy, owner UI and soak remain.
