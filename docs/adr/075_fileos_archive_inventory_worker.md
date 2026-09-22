# ADR-075 — Isolated FileOS archive inventory before member extraction

Status: accepted design; implementation pending.

## Context

FOS-Master has a well-tested recursive archive primitive, but it writes a destination
tree and returns paths. MasterBrain needs immutable, source-neutral child identities,
bounded untrusted parsing and a container boundary that cannot write beside the source
or expose runtime paths. Returning as much as 256 MiB of member bytes through the
current JSON pipe would also violate memory/output bounds.

## Decision

Adopt the donor's ZIP/TAR recognition, traversal/link/encryption refusals, cumulative
budgets, depth semantics and explicit skip/bomb accounting through a dedicated
in-memory inventory worker. The first contract returns only a deterministic member
manifest with safe relative locators, hashes, sizes, nesting/provenance and closed
outcomes. It never returns member bytes or text and never publishes search documents.

The request is bound to immutable DataCore source version, locator, SHA-256, size,
media type and exact archive bytes. The response repeats that identity and is treated
as wholly untrusted by the parent. Both request and result are closed, duplicate-key
rejecting and byte-limited.

The accepted donor defaults remain the expansion policy: 256 MiB total declared
uncompressed bytes, 64 MiB per member, 2,000 files, 100× ZIP ratio and depth three.
A separate compressed-input limit is mandatory for the isolated pipe. All nested
containers share one global budget. Only ZIP and TAR families are accepted; 7z is
explicitly deferred.

Duplicate safe member locators refuse the archive manifest instead of adopting donor
last-write-on-disk ambiguity. Bomb-suspected archives may return diagnostic accounting
but publish no child evidence. Corrupt archives may report verified members preceding
the fault as partial, but later publication requires a separate persistence ADR.

## Provenance and parity

The donor source/test hashes and 47-test baseline are recorded in
[the archive plan](../FILEOS_ARCHIVE_EXTRACTION.md). A live-donor golden harness
normalizes temporary roots only and compares member identities, hashes, sizes, order,
refusal classes, depth, bomb state and counts. Expected duplicate/bomb policy
differences are named assertions, never broad ignored fields.

## Non-goals

This ADR adds no archive persistence, member-byte retrieval, text/document extraction,
OCR, provider access, watcher, scheduler, file effect, public upload or FileOS cutover.
`zip_index.py` deletion behavior and `archive_manager.py` move/retention behavior are
explicitly excluded.

## Acceptance and rollback

The contract, in-memory implementation, donor harness, adversarial/property/fault
tests and dedicated restricted-image inspection must pass before integration. Rollback
removes the new isolated worker; existing FileOS and donor behavior remain unchanged.
