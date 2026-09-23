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

## Implemented MasterBrain boundary

The accepted first implementation is an isolated, in-memory **archive inventory
worker**. A
closed source-bound request carries one immutable archive version and its exact bytes.
The worker has no network, mounts, credentials or source access and returns a bounded
manifest only:

- archive format and contract/processor version;
- ordered safe relative member locator, SHA-256, declared/observed size, media hint,
  nesting depth and parent-container locator;
- explicit extracted/deferred/refused/failed status with a closed reason code;
- total member/byte counts, bomb state and complete/partial state.

The inventory response returns neither member bytes nor extracted text. This keeps it
bounded and lets DataCore record immutable child identities/provenance without trusting
paths. ADR-077 now implements a separate explicit read of one persisted, non-container
member with an 8 MiB response cap, independent parent hash verification and no
persistence. No archive is silently expanded into search.

The worker preserves donor limits and adds a 32 MiB compressed-input bound required by
the 512 MiB pipe/container memory budget. ZIP/TAR parsing uses `BytesIO`; nested member
bytes count against the same global budget. Duplicate safe locators, encrypted members,
links, absolute/traversal paths and unsupported formats fail closed. The dedicated
image is inspected before bytes enter it and runs with no network, mounts, writable
root, credentials, added capabilities or logs.

## Parity and acceptance

The golden harness builds each synthetic archive once, runs the pinned donor into a
temporary directory, hashes its normalized leaves, and compares the MasterBrain manifest
on ordering, safe locators, hashes, sizes, skips, bomb/depth state and accounting. It
must retain explicit expected differences for duplicate-name refusal and bomb
publication policy.

Acceptance status:

1. **Passed:** adopted donor cases plus the live-donor 47-test baseline.
2. **Passed:** hostile path normalization and cumulative nested-budget tests.
3. **Passed:** corruption/short-read, output-limit and worker-failure tests.
4. **Passed:** dedicated immutable image and actual no-network/read-only/no-mount
   inspection/invocation in hosted CI 35780244211.
5. **Passed:** PostgreSQL append-only/RLS/replay/concurrency/search-non-effect tests and
   populated restore for the hash-only manifest ledger.
6. **Passed:** source bytes remained immutable and FOS-Master stayed clean at the pinned
   commit.
7. **Passed:** one-member forced-RLS/current-version resolution, no-follow source
   revalidation, nested identity, true output-cap, hostile/fault and real restricted-
   container checks in CI 35789652225 and restore 35789652166.

No archive child becomes searchable and no FileOS cutover is authorized by this
inventory tranche.
