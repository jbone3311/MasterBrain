# ADR-218 — Worker-observed FileOS text replay for a reviewed tier

Status: implemented for fictional local testing on an open PR; hosted,
independent restore and merged-main gates remain open.

## Context

ADR-217 pins a human document-authority classification to recorded evidence
and text hashes, but those stored digests alone do not show that a FileOS
source file can still be confined, read and normalized. ADR-189 already
performed this check privately for one statement proposal. A source-tier
review needs the same proof without becoming a financial claim.

## Decision

Move the exact byte-to-text proof into DataCore and use one shared confined
read/replay operation for both ADR-189 statements and ADR-218 source-tier
reviews. The former import path remains a compatibility re-export. The
read is bounded to 1 MiB, denies symlink/path escape and changed files, checks
the bound physical root, hashes the returned bytes, repeats the supported
normalizer and compares the entire normalized body and digest. An authorized
worker checks the current source/grant/exclusion, review, document and version
basis before and after the filesystem read; the second check holds source and
item locks through receipt insertion. Migration 0076 stores one append-only,
tenant-scoped replay receipt per review. A separate SQL trigger enforces its
cross-table identity, current FileOS kind/status/version, pinned hashes,
root binding and reviewer-quote occurrence. Replays are idempotent only for
the same bound receipt. No source file is modified.

This records that the worker observed a matching file **at replay time**.
It does not guarantee that the file remains unchanged after the operation,
that a PDF/OCR/spreadsheet was completely extracted, that a document's
claimed issuer is authentic, that multiple sources independently corroborate
a value, or that a financial claim is approved. This ADR introduced an
internal operation; ADR-219 later adds a selected, authenticated operator
command. There is no public API route or unattended live-root run.
FOS-Master remains untouched.

## Acceptance and next gate

Fictional PostgreSQL tests must cover byte/text hash replay including BOM and
line-ending normalization, unchanged statement behavior, grants, wrong root,
changed file, symlink, source-version race, concurrent idempotence, SQL guard
and immutable protected storage. Full synthetic and hosted gates remain
required. Next prove PDF/OCR and spreadsheet extraction completeness with
explicit coverage/unsupported states, add the equivalent authorized Email
source-byte path, and define a restricted operational worker command. Only
after those and conflict/issuer review may a separate ADR propose using tier
evidence in a financial-claim publication gate.
