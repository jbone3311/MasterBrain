# FileOS donor-policy candidate ledger

DC-002I is a **nonpublishing** bridge between the pinned FOS-Master inventory
policy and a future MasterBrain DataCore manifest. It does not change the current
FileOS snapshot, importer, database, search path, or FOS-Master. Its decision is
[ADR-112](adr/112_fileos_donor_candidate_ledger.md).

`build_fileos_donor_candidate(root, source_id=..., observed_at=...,
metadata_only=False)` runs one bounded, root-confined donor-policy shadow scan.
The result has `candidate_version: masterbrain-fileos-donor-candidate-v2` and
`publishable: false`; it deliberately has no `manifest_version`, so the existing
v1 importer rejects it. The source ID and timezone-aware observation time are
required. A private physical-root binding, the pinned donor commit, policy
profile, hash limit, and no-follow setting identify what was observed. Callers
must keep the ledger private: locators may reveal personal folder or file names.

The four disjoint, sorted ledgers are:

| Ledger | Meaning | May create a source version? |
|---|---|---|
| `hashed` | A regular file with donor-policy SHA-256, byte size, media type and stable item/version IDs | Candidate identity only; no evidence is published |
| `deferred` | `no_hash`, `dataless` or `oversize` observation with locator, size and stable item ID | **No** version, digest, document, chunk, or searchable text |
| `exclusions` | Explicit donor junk, operational or nonregular skip | No |
| `errors` | Unreadable, changed, skipped-symlink or root-drift observation | No; coverage is uncertain |

No downstream consumer may treat a deferred locator or an error as proof that a
file is absent. A SHA-less donor row cannot be upgraded into evidence by
inventing a digest or reusing a previous version ID. Counts must match their
ledgers; duplicate/overlapping locators, malformed hashes/states and record
overflow fail closed. Root drift is recorded as an error. This ledger is not a
completion receipt and cannot authorize absence inference.

[ADR-156](adr/156_shadow_symlink_target_boundary.md) advances the nonpublishing
shadow profile and candidate to v2: any symlink, including one pointing to a
directory, is a `symlink_skipped` error without asking the target's type.
Previously sealed v1 packets remain historical, but are not newly staged or
sealed as v2; a fresh scan and review is required. This changes no publishable
FileOS inventory, source data or donor repository.

## Verification boundary

The pinned-donor comparator uses a fictional 3,000-file temporary root and
isolated in-memory SQLite to check exact path, size and SHA for ordinary and
metadata-only observations, plus replay and one changed file. Focused tests
cover malformed and overlapping ledgers, no-follow/root swaps and v1 rejection.
These checks establish synthetic behavior at the pinned donor commit only.
They do **not** prove real cloud-placeholder behavior, macOS/other-platform
equivalence, live-source coverage, performance at production scale or a safe
policy switch. Hosted CI does not contain the donor checkout, so its green
checks cannot replace the local donor comparison.

## Next gate

A separate v2 publication design must specify whether and how metadata-only
observations persist, how freshness and absence are represented, how a v1 source
transitions without false deletion, and how rollback works. Then add
PostgreSQL/RLS/restore tests, broader fault/platform parity, read-only live
shadow with owner authorization, and explicit owner acceptance before any
FileOS cutover. FOS-Master remains the operational reference throughout.
