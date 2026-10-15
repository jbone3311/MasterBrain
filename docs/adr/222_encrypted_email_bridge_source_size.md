# ADR-222 — Preserve encrypted Email source size in DataCore

Status: implemented with fictional encrypted MIME on an open PR; hosted
exact-head checks remain open.

## Context

Email can retain original MIME either inline or in the private authenticated
encrypted blob store. The existing Email-to-DataCore bridge read
`octet_length(raw_objects.raw_mime)` for its source-version size. For an
encrypted object, `raw_mime` is deliberately `NULL`, so the bridge tried to
insert a `NULL` into `brain_source_versions.size_bytes` and failed. That
blocked a legitimate encrypted Email source from joining the shared Brain
index even though its current legacy evidence was available.

## Decision

Read `raw_objects.raw_size`, the database-generated size across inline and
encrypted storage, when creating the DataCore source version. Keep all
existing tenant, current-version, grant, hash and document checks. No MIME
or blob bytes are returned by the bridge, and no external mail is fetched.
The change is backward-compatible for inline evidence and does not rewrite
previous versions.

## Acceptance and next gate

An isolated fictional encrypted object must bridge successfully, retain the
source MIME SHA-256 and exact byte count, be recoverable through the existing
authorized blob read, and leave only ciphertext on disk. The inline bridge
regression must still pass. Run the full disposable-PostgreSQL suite and
hosted exact-head/restore gates before merge.

This repairs source identity; it is **not** independent Email byte-to-text
replay, source-tier attestation, attachment extraction completeness, a
financial claim, or permission to connect a live mailbox. The next gate is a
separately authorized, current-evidence replay from retained MIME that
recomputes the bridge's normalized text under a pinned parser version and
records an immutable point-in-time receipt.
