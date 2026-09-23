# Private archive-image OCR operator contract

Status: checkpoint 5C implemented and accepted at runtime revision `f658ace`;
[CI 35836198307](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35836198307)
and [restore 35836198414](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35836198414)
are green.

## Purpose and invocation

Publish the nonempty OCR text of one explicitly selected current image member from an
already persisted archive inventory. The private command is:

```sh
MASTERBRAIN_DSN='postgresql://least-privileged-runtime/...' \
  masterbrain fileos archive-image \
  --config /private/operator/archive-member.json \
  --inventory-id archive_inventory_0123456789abcdef0123456789abcdef \
  --member-locator images/receipt.png \
  --idempotency-key 93c5a004-81ab-45b6-8652-e8ced2b40e47 \
  --check
```

The inventory, locator and UUID are supplied by the operator. The command has no
discovery or automatic key generation. The locator is private untrusted metadata and
must never appear in normal output. Retry an uncertain execution using the exact same
selection and key.

## Configuration and authority

The existing closed version-1 archive configuration gains one optional field,
`image_ocr_image_id`, required for this command alone. It is a pinned lowercase
`sha256:` image digest distinct from `archive_image_id` and `document_image_id`.
The configuration also binds the absolute authorized root, absolute Docker binary,
owner-private credential and token files, and deployed code revision. The DSN comes
only from `MASTERBRAIN_DSN` and never from command output or a config file.

An expiring worker identity must have exactly `brain.source.ingest` and
`brain.document.publish`. The database role must be non-owning, non-superuser and
unable to bypass forced RLS. Both workers use their existing restricted images and
receive no database credential.

## Check and execution

`--check` validates the argument shapes, closed/private configuration, root, pinned
image IDs, current worker identity and database role. It does not query the archive
inventory, read source bytes, construct Docker workers, execute OCR, write a receipt
or consume the key. It reports only configuration validity, that execution was not
verified, the operation name, and false source/data effects.

Normal execution:

1. Authenticate and preflight the database role; resolve the exact current,
   non-container member through the existing forced-RLS selector.
2. Reauthenticate before source access. The archive worker reopens the current parent
   without following a symlink and releases only the hash-bound member in memory.
3. The separate image worker verifies format/signature, fully decodes one frame and
   returns bounded OCR through its closed contract. Bytes and decoded pixels are
   discarded after the handoff.
4. Require a complete nonempty `bounded_image_ocr_v1` result. Reauthenticate, then
   publish with the 5B wrapper, which validates metadata and binds exact processor,
   parent, inventory, member and idempotency identities inside a transaction.
5. Reauthenticate before returning a content-free receipt. An empty, deferred,
   failed or unsupported extraction produces no publication.

The response may contain only operation name, opaque inventory/source/item/version/
evidence/document IDs, chunk count, changed/replay state and `source_effects: false`.
It contains no locator, path, OCR text, format metadata, dimensions, raw bytes,
worker details, credentials or underlying exception. Any refusal is one generic
content-free error. A successfully published derivative remains in retained-history
retrieval; this command does not add a current archive-image search layer.

## Acceptance

- Closed config rejects unknown fields, missing/invalid OCR image digest, unsafe
  locators, non-private files and wrong worker scopes.
- `--check` performs no selection, source read, worker construction or write.
- Flat and nested image members publish one exact derivative; replay is idempotent,
  while changed input or reused keys conflict.
- Blank/unsupported/over-limit/animation/format-masquerading images, worker faults,
  stale parents and revoked identity leave no partial derivative.
- CLI and controller responses contain no sensitive source or credential material.
- Real two-container, PostgreSQL, restore, donor parity and source-immutability gates
  remain green.

This checkpoint authorizes no preview, batch, automatic archive traversal, scanner
decision, scheduler, public route, current search, source effect or FOS-Master cutover.

The accepted hosted run passed 2,652 PostgreSQL-backed Python tests, 134 browser
contracts and all restricted worker/container gates. The populated restore passed.
These gates do not establish live-source or production acceptance.
