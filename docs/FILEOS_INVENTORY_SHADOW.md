# FileOS whole-inventory shadow comparison

ADR-093 authorizes a synthetic-only comparison of the pinned FOS-Master scanner
against MasterBrain's current `snapshot_tree`. This is a measurement gate, **not** a
snapshot policy change, FileOS enrollment, publication, cutover or donor rewrite.

## Safe execution

```sh
PYTHONPATH=src python3 scripts/fileos_inventory_shadow.py \
  --fos-repo ../FOS-Master --stress-files 3000
```

The script verifies FOS-Master commit
`218d5caec2f20b9047fd3eb8e027dc671acf0c15`, scanner SHA-256
`bf4a9bb46275bb3d9ae429335520b333541dfbbddbd0c2ec4ddef2d9873d1073`
and classifier SHA-256
`12110b1b5404c31172d65878a9327bf8f415f8d343b668aa5982948c840da437`
before loading the donor scanner. It creates a fresh fictional tree in a temporary
directory, overrides only the donor's root resolver for that call, and requires an
in-memory SQLite connection. It invokes `scan_domain` directly; never the donor CLI
or its configured database/registry. MasterBrain only runs `snapshot_tree`; it does
not import, complete, activate or publish the manifest.

## Measured baseline

On 3,000 generated ordinary files plus fixed fictional edge cases, the current
policies agree on **3,002** common hashable items: size and SHA-256 match. There are
exactly six reason-coded path differences:

| Present only in | Relative path | Why |
|---|---|---|
| Donor | `.db/child.txt`, `metadata.db` | MasterBrain's legacy dedupe default excludes `.db` components/extensions |
| MasterBrain | `.trashes/old.txt` | Donor scanner prunes named system-junk directory |
| MasterBrain | `_SYSTEM/state.json` | Donor scanner prunes FOS operational directory |
| MasterBrain | `_status.html`, `~$draft.docx` | Donor scanner ignores generated status and Office lock files |

Both keep `.Investor Letters` as real hidden content. The harness fails if this exact
difference set changes without review; it does not normalize away a new gap or treat
a null donor digest as equal to a MasterBrain SHA-256.

The pinned donor's replay is unchanged; a changed fictional report updates one row;
a single removal removes one. A `--no-hash` donor scan catalogs 3,004 rows with null
SHA-256; 3,002 would otherwise be common MasterBrain items but are explicitly
`donor_hash_deferred`, never claimed as publishable parity. Donor `--rehash` fills all
3,004 hashes and restores the original comparison result. When 1,502 of the
remaining rows disappear, the donor refuses mass pruning and retains those rows;
the fresh MasterBrain snapshot omits them. This is measured divergence, not a
recommendation to copy donor deletion behavior into DataCore.
An internal and an outside-root file symlink are a separate explicit divergence:
the donor scanner follows and hashes both, while MasterBrain marks both
`symlink_skipped`. The future integrated adapter must not inherit the donor's
outside-root read behavior.

## Limits and next gate

The comparator covers paths, sizes, hashes, ordinary change/removal, replay,
metadata-only hashing, and the donor mass-prune tripwire on synthetic files. Donor
document labels/CRC and MasterBrain media types/IDs are not equivalent fields.
Cloud dataless placeholders, >100 MiB/2 GiB policy boundaries, unreadable
directories and source races still need explicit adversarial cases before any
integrated inventory-policy change. The future policy ADR must version manifests,
represent metadata-only/oversize candidates without calling them complete evidence,
prevent policy-only absence events, and prove replay, rollback and search visibility
on consecutive completed runs. FOS-Master remains the operational reference.
