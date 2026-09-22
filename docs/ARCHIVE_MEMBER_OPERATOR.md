# Private archive-member text operator plan

## Purpose

Expose the checkpoint 4Q primitive as one explicit private `masterbrain` command. The
operator names one accepted archive inventory, one virtual member locator and one
idempotency key. It revalidates the current FileOS source, reads the exact member in
the immutable archive image, normalizes eligible text and publishes one derivative.

## Closed configuration

The owner-private version-1 configuration contains only:

- absolute FileOS `root`;
- absolute `credentials_file` and `token_file`;
- immutable `archive_image_id` and absolute `docker_binary`;
- non-secret `code_revision`.

Configuration and credential files use the existing owner-private/no-symlink checks.
The expiring worker has exactly `brain.source.ingest` and `brain.document.publish`.
The DSN remains environment-only and the runtime role is preflighted before execution.

## Sequence

`--check` authenticates, validates the private configuration, root, immutable image ID,
runtime database role and argument shapes. It does not query the inventory, read the
archive, invoke Docker or consume the idempotency key.

Normal execution:

1. authenticates and preflights the least-privileged runtime role;
2. resolves the exact current non-container member through forced RLS;
3. reauthenticates before bytes leave the configured root;
4. performs the no-follow source revalidation and fixed isolated member read;
5. normalizes only accepted text/Markdown/HTML/CSV within the 1 MiB text cap;
6. reauthenticates before the publication transaction;
7. publishes through the checkpoint 4Q replay/current-parent fences;
8. reauthenticates before returning a content-free receipt.

Output contains only opaque source/item/version/evidence/document identities, inventory
ID, chunk count, changed/replay state and `source_effects: false`. It never returns a
member locator, source path, raw bytes or normalized text.

## Non-goals

No preview enumeration, glob, batch, cursor, automatic sibling continuation, public
API, scheduler, current-search activation, raw export, archive upload, PDF/Office/OCR,
FileOS write/effect or FOS-Master cutover is authorized.

## Acceptance

- closed config and argument tests reject unknown fields, relative/symlink/private-mode
  failures, mutable image references and unsafe locators;
- check mode performs authentication/database preflight but no target query, Docker
  invocation, receipt or source access;
- exact scopes, repeated reauthentication and revoked-credential failure are proven;
- one flat and one nested member publish with content-free output and exact replay;
- stale parent, unsupported/empty/oversized member, processor fault and key reuse fail
  with one generic error and no partial derivative;
- full PostgreSQL, restore, real archive image, donor parity and source immutability
  gates remain green.
