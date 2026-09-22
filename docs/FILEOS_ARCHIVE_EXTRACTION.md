# FileOS archive inventory and extraction plan

## Pinned donor audit

DC-004C starts from FOS-Master commit
`218d5caec2f20b9047fd3eb8e027dc671acf0c15`:

```text
a1d20a266313d7b2c36af3ffc78311ee1999824cfe933883a3ed4f87223d21ba  _SYSTEM/tools/archive_unpack.py
a5b177791a3045661b42c1aa4692b54546c8ce18711f00d7ca74fd08c055dfbc  _SYSTEM/tests/test_archive_unpack.py
```

The donor suite passes **47 tests** with caches and bytecode redirected outside the
unchanged checkout. The primitive is standard-library-only and recognizes ZIP plus
plain/gzip/bzip2/xz TAR by content. It recursively expands nested containers and has
shared per-run limits of 256 MiB declared uncompressed bytes, 64 MiB per member, 2,000
files, 100× ZIP member ratio and depth three.

The test corpus covers valid flat/nested ZIP and TAR, relative/absolute/backslash
traversal shapes, ZIP symlinks, TAR symlinks/hardlinks/special members, encrypted ZIP,
ratio/member/count/total bombs, nested bomb evasion, default depth, retained container
accounting, corrupt/truncated archives, partial-target cleanup, duplicate/NUL/overlong/
control-character names, missing/non-archive inputs and configuration drift.

Transitive runtime dependencies are only `zipfile`, `tarfile`, `stat`, `pathlib` and a
best-effort donor error logger. `intake_pipeline.py`, `doc_extract.py` and
`email_core.py` call it through temporary work directories. `intake_preflight.py`
reports its caps. `zip_index.py` is a separate SQLite catalog/delete tool and
`archive_manager.py` is a move/retention/delete tool; neither enters DataCore archive
extraction.

## Compatibility findings

- Donor callers include `.7z` in extension routing, but `archive_unpack.py` has no 7z
  reader and returns “not a recognized archive.” MasterBrain will report 7z as
  unsupported, not imply extraction.
- The donor discovers mutable `spoke_config.json` by walking from the process working
  directory. MasterBrain uses a closed versioned request; ambient config discovery is
  not migrated.
- The donor materializes into a caller-provided directory and returns absolute paths.
  MasterBrain may not expose host/container paths or write beside source evidence.
- Duplicate member names overwrite the first file on disk while the donor accounts
  only the first entry. MasterBrain will refuse the ambiguous member set rather than
  publish content whose identity disagrees with accounting.
- A donor bomb/corruption may leave prior safely extracted files in its result. The
  parity harness records that behavior, but MasterBrain will not publish any child
  evidence from a bomb-suspected archive. Partial corruption outcomes remain explicit.
- Donor CLI text, ambient logging and destination-directory layout are not shared
  contracts. Member ordering, eligibility, refusal reason class, bomb state, depth and
  byte/count accounting are parity inputs.

These are deliberate hosted safety adaptations, not unexplained parity normalization.

## Planned MasterBrain boundary

The first implementation is an isolated, in-memory **archive inventory worker**. A
closed source-bound request carries one immutable archive version and its exact bytes.
The worker has no network, mounts, credentials or source access and returns a bounded
manifest only:

- archive format and contract/processor version;
- ordered safe relative member locator, SHA-256, declared/observed size, media hint,
  nesting depth and parent-container locator;
- explicit extracted/deferred/refused/failed status with a closed reason code;
- total member/byte counts, bomb state and complete/partial state.

It returns neither member bytes nor extracted text. This keeps the response bounded
and lets DataCore record immutable child identities/provenance without trusting paths.
A later explicit member-read contract can return one hash-bound bounded member to the
existing text/document workers. No archive is silently expanded into search.

The worker preserves donor limits initially and adds a closed compressed-input bound
required by the pipe/container memory budget. ZIP/TAR parsing uses `BytesIO`; nested
member bytes count against the same global budget. Duplicate safe locators, encrypted
members, links, absolute/traversal paths and unsupported formats fail closed.

## Parity and acceptance

The golden harness will build each synthetic archive once, run the pinned donor into a
temporary directory, hash its normalized leaves, and compare the MasterBrain manifest
on ordering, safe locators, hashes, sizes, skips, bomb/depth state and accounting. It
must retain explicit expected differences for duplicate-name refusal and bomb
publication policy.

Acceptance requires:

1. all adopted donor cases plus live-donor 47-test baseline remain green;
2. property tests for path normalization and cumulative nested budgets;
3. fault tests for truncation, short reads, output limit, timeout and worker death;
4. a dedicated immutable container image and actual no-network/read-only/no-mount
   inspection gate;
5. PostgreSQL append-only/RLS/replay tests before any member manifest is published;
6. source archive hash/mtime unchanged and FOS-Master clean at the pinned commit.

No archive child becomes searchable and no FileOS cutover is authorized by this
inventory tranche.
