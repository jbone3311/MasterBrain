# ADR-093 — Compare FileOS inventories in isolated shadow mode

Status: implemented synthetic-only harness with hosted CI green on PR #15; review
pending. No snapshot policy switch, source enrollment, publication or cutover authorized.

## Context

The pinned FOS-Master `scan_domains.py` uses its shared `junk_filter.py`, keeps
ordinary dot-directories as content, and can catalog no-hash/cloud/oversize files.
The current MasterBrain `snapshot_tree` uses the older donor dedupe exclusions,
requires a SHA-256 for each included item, and caps included files at 100 MiB by
default. Its `masterbrain-fileos-snapshot-v1` manifest may be imported, completed,
used to infer absence, and indexed. Switching exclusions without a policy/version
decision could mark previously observed files absent and alter current search.

## Decision

Build a **read-only synthetic shadow comparator** before changing FileOS snapshots.
It must load only the pinned donor scanner source and classifier after commit/hash
verification, route the scanner to an explicit disposable synthetic root and an
in-memory SQLite database, and call `scan_domain` directly. Never invoke the donor
CLI, live domain resolver, registry writer, or default database—even `--dry-run` on
the CLI may open or migrate that database. The MasterBrain side calls its current
`snapshot_tree` without importing or publishing the manifest.

Normalize stable relative paths, sizes and SHA-256 on the common hashable set.
Keep donor-only, MasterBrain-only, hashless/deferred, changed-hash and incomplete
cases separate with explicit reason codes; do not hide them by dropping rows or
calling null hashes equivalent. Donor document labels, CRC, timestamps, SQLite row
IDs and MasterBrain stable IDs are recorded where useful but are not assumed to be
the same contract. Fixture-expected policy differences may be accepted only when
enumerated exactly; any other divergence fails the harness.

This ADR does not change DC-001 dedupe defaults, `snapshot_tree` v1, publication,
completion, absence, activation, current search, or FOS-Master. A later ADR must
decide a versioned FileOS inventory policy, metadata-only/oversize representation,
coverage and mass-loss guards, replay/rollback and policy provenance before an
integrated switch.

## Verification and rollback

Use synthetic fresh/replay/changed/removed/mass-loss and no-hash/rehash cases,
including named junk, FOS operational folders, hidden content and `.db` paths.
Exercise symlink/race/unreadable and size-bound behavior as explicit differences,
not parity claims. Stress at least 3,000 paths. Prove the donor source checkout is
unchanged, no live path/database/registry is touched, and no MasterBrain publication
occurs. The comparator must fail when expected differences drift or a common SHA-256
changes. Hosted CI, documentation and restore gates precede review.

Rollback is to stop using the comparator; no schema, source or retained evidence is
changed by this decision. FOS-Master remains the operational reference.

## Alternatives rejected

- Switch snapshots immediately: prior completed manifests and absence/search state
  would be reinterpreted without versioned policy and rollback proof.
- Compare only the copied classifier: name parity does not prove inventory, hash,
  failure or mass-loss behavior.
- Run the donor CLI with `--dry-run`: it still accesses the configured donor database
  and may migrate schema outside the synthetic fixture.
