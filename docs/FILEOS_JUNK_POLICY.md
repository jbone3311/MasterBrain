# FileOS inventory classifier extraction

The pinned FOS-Master scanner and reconciler both import
`_SYSTEM/tools/junk_filter.py`. MasterBrain now carries a behavior-identical
copy at `src/masterbrain/datacore/fileos_junk_filter.py` for a future shared
FileOS inventory policy. The donor is `jbone3311/FOS-Master` commit
`218d5caec2f20b9047fd3eb8e027dc671acf0c15`; its SHA-256 is
`12110b1b5404c31172d65878a9327bf8f415f8d343b668aa5982948c840da437`.
The target SHA-256 is
`0bc54e3597ed90549f505695c9912882c7c7b1cdbd82fade67eb7797c69f3b3b`.
The **only** difference is two `type: ignore[assignment]` comments in the donor's
standalone self-test, needed for MasterBrain's strict mypy gate. Removing those
comments reproduces the pinned donor's exact bytes; the test suite asserts this.
No donor file was edited.

This is **extracted and parity-tested, not integrated** into `snapshot_tree`,
`dedup`, reconciliation or publication. The copied function classifies names and
relative paths in memory; it does not read or change files or databases. The live
donor harness compares all public classifications and directory pruning over 3,000
deterministic synthetic paths. Run it with:

```sh
PYTHONPATH=src python3 scripts/fileos_junk_parity.py --fos-repo ../FOS-Master --cases 3000
```

The donor's scanner filter is **not** its dedupe policy. FOS scanner ignores Office
locks, `_status.html`, named junk directories and FOS operational directories, but
keeps `.Investor Letters` and `metadata.db` as content. The existing DataCore
snapshot uses the extracted dedupe defaults, which can include some donor junk and
exclude `.db` paths. Silently changing dedupe defaults would break DC-001 parity.

Before wiring the copied classifier into FileOS snapshots, decide the source-level
inventory policy in an ADR, test the resulting manifest and exclusion counts against
the pinned scanner, and distinguish donor metadata-only/placeholder records from
MasterBrain's hash-required publishable evidence. Do not route this policy into Email
or mutate existing evidence. Full scanner shadow parity, mass-loss/race/fault tests,
and an approved cutover remain open.
