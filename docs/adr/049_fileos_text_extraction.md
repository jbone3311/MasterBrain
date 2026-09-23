# ADR-049 — Read-only FileOS text extraction tranche

Status: accepted for the additive prototype tranche on 2026-09-22.

## Decision

The first FileOS extraction tranche supports bounded `.txt`, `.md`, `.html`, `.htm`
and `.csv` source versions. It adapts the encoding, HTML text and CSV behavior from
FOS-Master `_SYSTEM/tools/doc_extract.py` at pinned commit
`218d5caec2f20b9047fd3eb8e027dc671acf0c15`, while adding MasterBrain's source-bound
evidence checks and publication limits.

Before reading, the adapter resolves a safe relative locator under the enrolled root,
refuses symlinks, checks the declared size and reads at most 1 MiB. After reading it
checks file identity/metadata stability and verifies the full SHA-256 against the
immutable source version. Changed, missing, oversized, unsupported, empty and failed
inputs receive distinct accounted outcomes. No source file is modified.

Confident Unicode BOMs and strict UTF-8 are decoded deterministically. Latin-1 is the
last fallback and is labeled `encoding_uncertain`. HTML excludes head/script/style
content and separates structural/table elements. CSV uses a real line iterator so
quoted embedded newlines survive. Extracted text is published through the Checkpoint
2 immutable document/chunk/provenance path; one file failure does not discard sibling
successes.

## Deferred

PDF, Office, legacy XLS, archives, email containers, images and OCR require dedicated
isolated workers and format corpora. This tranche adds no FileOS writes, automatic
root enrollment, model calls or FOS-Master cutover.

## Verification and rollback

Tests cover BOM/UTF-16/Latin-1, CRLF, HTML active-content removal, table separation,
quoted CSV newlines, binary/NUL content, traversal, symlinks, hash/size drift,
oversize, unsupported/empty accounting and sibling-failure isolation. The live-donor
parity harness compares supported extraction semantics against the pinned FOS source.
Rollback is to stop the additive adapter; source files and FOS-Master remain unchanged.
