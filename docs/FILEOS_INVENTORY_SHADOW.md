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

Hosted [CI 35852211467](https://github.com/jbone3311/MasterBrain/actions/runs/35852211467)
passed on PR #15. Its two donor-checkout skips are expected: CI does not include
FOS-Master, so the pinned-donor comparison was run locally. PR #15 did not trigger
a restore drill under the workflow's path filters; PR #14's underlying restore
[passed](https://github.com/jbone3311/MasterBrain/actions/runs/35852112586).

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

ADR-100's isolated follow-up routes MasterBrain snapshot hashes through confined,
descriptor-relative reads. Ordinary SHA/size parity and the explicit symlink
divergences were rerun locally against this change on 3,000 synthetic files:
3,002 ordinary SHA/size matches, six known policy differences and two symlink
differences. Hosted gate and restore passed on code head `6e2eb8e` in PR #25.
FOS-Master remains pinned and unchanged.

## Synthetic fault and size boundary tranche

Focused live-donor tests now exercise two sparse, fictional size boundaries without
allocating gigabytes of disk. At 100 MiB + 1 byte, the pinned donor hashes and
indexes the file while the current MasterBrain snapshot excludes it. At 2 GiB + 1
byte, the donor catalogs a metadata-only row with null SHA-256; the test forbids
calling its hash reader for that file, and MasterBrain again excludes it. Both are
reason-coded `shared_size_limit`, not equal evidence. The sparse fixture skips on a
filesystem that cannot provide sparse allocation.

A deterministic donor read failure after a prior successful scan marks the path as
seen but leaves its old row unchanged; MasterBrain records `file_unreadable` and
publishes no item. A synthetic content mutation during MasterBrain hashing records
`changed_during_scan` instead of a mismatched item. A broken file symlink produces a
MasterBrain `symlink_skipped` error but no donor row, while neither scanner descends
through the synthetic directory symlink. These tests use only temporary roots and
an in-memory donor database. They do not authorize treating a retained donor row as
proof that the file was successfully read on the latest run.
Hosted [CI 35855259654](https://github.com/jbone3311/MasterBrain/actions/runs/35855259654)
passed on the fault-test commit in PR #16; the live pinned-donor tests passed
locally and skip in hosted CI because that runner has no donor checkout.

## Synthetic scanner-edge tranche

Four further tests use the pinned donor scanner on temporary fictional files and
in-memory SQLite. A simulated dataless flag yields a donor metadata-only row with
null SHA-256 and no donor byte read, while MasterBrain hashes the locally present
fixture. This tests the decision branch, **not** a real cloud placeholder or
materialization behavior.

A simulated unreadable directory after a successful one-file donor scan causes the
donor to remove that old row: its walk has no error callback and the one missing row
is below the mass-prune threshold. MasterBrain records `directory_unreadable` on
the same synthetic omission. In a separate donor-side race, changing a file inside
the donor hash call produces a row with the pre-change size and post-change SHA-256;
a later stable MasterBrain snapshot exposes a `common_size_mismatch`. These are
measured safety gaps, not accepted parity. Four unusual but valid names (leading
space, Unicode accent, emoji, embedded newline) retain exact locators through both
inventories and JSON serialization on the local test filesystem.
Hosted [CI 35857585834](https://github.com/jbone3311/MasterBrain/actions/runs/35857585834)
passed on PR #17's code head; donor-specific tests skip on hosted CI without a
FOS-Master checkout.

## DC-002G isolated donor-policy profile

ADR-111 adds a second, **nonpublishing** DataCore comparison path. It uses the
extracted donor classifier to prune junk/operational directories and junk files,
retains hidden content and `.db` files, hashes ordinary files within the donor's
2 GiB limit through DataCore's no-follow confined reader, and labels oversize,
simulated dataless and explicit no-hash rows as metadata-only. Its output has a
`shadow_profile` marker and `publishable: false`; it is not a `snapshot_tree`
manifest and cannot be completed or indexed.

Run only against a synthetic temporary root and a pinned donor checkout:

```sh
PYTHONPATH=src python3 scripts/fileos_donor_policy_shadow.py \
  --fos-repo ../FOS-Master --stress-files 3000
```

The local comparison matched 3,004 ordinary path/size/SHA rows (3,000 generated,
four fixed), 3,004 replay rows, one changed-file replay, and 3,004 explicitly
metadata-only no-hash rows. Six excluded locators are accounted separately. A
100 MiB + 1 sparse file is hashed by both scanners; a 2 GiB + 1 sparse file is
metadata-only and **not** counted as hash parity. The intentional symlink refusal,
real cloud placeholders, unreadable directories, platform filename collisions,
source-root races and mass-loss behavior remain separate acceptance gates. This
does not change the six-difference snapshot-v1 baseline above or FOS-Master.

DC-002H tightens this nonpublishing profile: metadata-only and ordinary leaf
observations now use a descriptor-relative, no-follow stat bound to the root's
initial device/inode, without opening file bytes. A second traversal refuses
locator replacement. A root changed before a walk iteration stops the scan and
records an error instead of cataloging outside metadata. Special nonregular
leaves retain their prior exclusion outcome. Synthetic ancestor,
leaf and root-swap regressions pass; the pinned 3,000-file comparator still has
3,004 ordinary/replay/change and metadata-only matches. These checks do not
prove real Dropbox/OneDrive placeholder behavior or make a scan publishable.

ADR-152 also confines directory enumeration in this separate donor-policy
shadow. A synthetic child-directory symlink swap had allowed `os.walk` to
list an outside junk filename and return it as an exclusion, even though the
confined leaf reader refused bytes. Each directory is now reopened through
no-follow descriptors and rechecked after listing; descendant, nested-ancestor
and after-open move regressions return only a directory coverage error. The pinned
3,000-file comparator still
matches 3,004 ordinary rows with the six documented policy gaps. This does
not change the donor scanner or authorize live-root shadow/cutover.

ADR-156 removes the remaining symlink-target type probe from that shadow.
Directory entries are checked for symlinks before no-follow directory
classification. File, directory and dangling links now share a
`symlink_skipped` coverage error; a directory link is no longer a safe
exclusion. The shadow profile and candidate version advance to v2 so an old
review packet cannot silently acquire the new policy. Ordinary donor parity
is unchanged. This still does not establish real cloud-placeholder or live
root acceptance.

## Filename representation probe (2026-10-06, PR #164 merged)

A new fictional corpus compares case variants and composed/decomposed Unicode
names. The cross-directory variant runs against the pinned FOS-Master scanner,
snapshot v1 and the nonpublishing donor-policy shadow on this Mac, checking
exact on-disk locators, independent SHA-256 values and JSON round-trip. The
same-directory sibling variant is conditional on the filesystem actually
representing four distinct files. This Mac folded a pair, so its two sibling
tests skipped rather than claiming parity; the 37 focused tests that ran passed.
The shared snapshot/shadow sibling probe passed on the capable hosted CI
filesystem in PR #164's exact-head run (3,149 tests passed twice, all 491
PostgreSQL-marked tests executed each time). CI has no FOS-Master checkout, so
its two donor-dependent tests skipped and donor sibling behavior on Linux is
not proved. No filename policy, publication authority or donor code changes here.

The follow-up case-sensitive probe adds 128 numbered upper/lowercase filename
pairs plus four named variants in one directory (260 fictional files). On a
temporary case-sensitive APFS image, the pinned donor scanner, snapshot v1 and
the nonpublishing donor-policy shadow agreed on exact locators and SHA-256
values; all 38 focused tests that could run passed. The two combined
composed/decomposed sibling tests still skipped on APFS. The conditional case
test skips on the ordinary Mac volume. Linux donor/Unicode parity remains open.

The next parity-harness tranche checks in exact, SHA-verified copies of the
pinned scanner and classifier under `tests/fixtures/pinned_fos_master/`.
The normal local comparison still uses the untouched sibling checkout;
hosted CI uses only the fixed test snapshot, not a cross-repository token.
The Linux gate explicitly requires the donor case and normalization sibling
corpora to execute instead of skipping. PR #167's code-head CI passed all
three such tests and both full suites, including all 491 PostgreSQL-marked
cases each time. The snapshot was absent from the API runtime image. This is
synthetic Linux parity for those filename cases, not a live cloud-placeholder,
fault-permission, invalid-byte-name or policy-cutover acceptance. The exact
hosted result is recorded in the build receipt.

## Invalid-byte name safety boundary

ADR-167 keeps surrogate-escaped, non-UTF-8 names out of portable DataCore
locators. Snapshot v1 and the nonpublishing donor shadow do not inspect the
affected file or descend into the affected directory. They report one opaque
`invalid_locator_encoding` error for its encodable parent, while preserving
valid siblings. V1 completion refuses this partial coverage; the donor-policy
transition candidate also refuses before any stage or approval. The pinned
FOS-Master scanner is unchanged. A Linux-required synthetic test creates
actual invalid-byte names and records its SQLite-text behavior; a Mac skip is
not counted as a parity pass. This is an intentional fail-closed difference,
not source-name repair or live FileOS cutover acceptance.

## Limits and next gate

The comparator covers paths, sizes, hashes, ordinary change/removal, replay,
metadata-only hashing, and the donor mass-prune tripwire on synthetic files. Donor
document labels/CRC and MasterBrain media types/IDs are not equivalent fields.
Real cloud dataless placeholders, permission-driven unreadable directories,
cross-platform normalization/case collisions and live invalid-byte-name
behavior still need platform-appropriate acceptance before any
integrated inventory-policy change. ADR-096 now versions the current snapshot
policy and refuses policy-only absence inference across complete runs; it does not
adopt the donor policy. A future integration decision must represent metadata-only/
oversize candidates without calling them complete evidence and prove replay,
rollback and search visibility on consecutive completed runs. ADR-097 adds
per-locator exclusion accounting and refuses a prior indexed file newly covered
by an exclusion or no-follow skip; that safety guard does not make donor and
MasterBrain scanner policies equal. FOS-Master remains the operational reference.
