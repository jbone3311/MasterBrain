# Test the MasterBrain synthetic alpha candidate

This guide is for `0.2.0a1` on a tested, merged checkpoint. Until the
`v0.2.0a1` tag exists, the version is a candidate, not a release. Use fictional
files and a disposable database only. Do not connect real mail, grant live roots,
upload private documents, expose the server, or delete/rename FOS-Master.

## What this test can prove

The shared MasterBrain CLI can read and hash a synthetic FileOS tree without
changing it; DataCore's common hash/dedupe behavior can be compared to the pinned
FOS-Master donor; the synthetic Email reader can be tried in a browser; and the
full test suite exercises Email, FileOS, shared persistence/retrieval, restricted
workers and a PostgreSQL restore in CI. None of these prove hosted operations,
real-account consent, production identity, live cloud-placeholder behavior or
FileOS cutover. The complete production gates remain in
[release acceptance](RELEASE_ACCEPTANCE.md).

## Trial A — read-only FileOS and donor parity

From this checkout, with `uv` and a supported security-patched Python runtime
(see [strict-runtime requirements](STRICT_RUNTIME.md)):

```sh
uv sync --locked --extra dev
uv run masterbrain fileos snapshot tests/fixtures/datacore_parity/corpus \
  --source-id alpha_files
uv run python scripts/datacore_parity.py --fos-repo ../FOS-Master --stress-files 3000
```

The snapshot prints a manifest of synthetic relative locators, hashes, sizes,
status codes and counts. It does not publish to PostgreSQL, read live data or
modify source files. The second command requires a separate local checkout of
the pinned FOS-Master donor at
`218d5caec2f20b9047fd3eb8e027dc671acf0c15`; it refuses another commit by
default. Review any differences by category. The documented inventory/symlink
policy differences are not authorization to change donor behavior or cut over.

## Trial B — fictional Email reader

Run the [reader preview](USER_TESTING.md) and follow its browser checklist:

```sh
uv run python tests/reader_preview.py --synthetic-preview
```

This is an in-memory UI trial, not a PostgreSQL or cross-source integration test.
Do not enter a real token or paste real email. Stop the local server with Ctrl-C.

## Trial C — disposable database-backed integration

Follow [local development](LOCAL_DEVELOPMENT.md) to initialize a new, disposable
PostgreSQL 17 instance and synthetic owner, run migrations, seed fictional mail,
then start the loopback UI. Never point the integration suite or restore drill at
an existing personal/production database. The full hosted CI and populated restore
results are recorded in [build receipts](BUILD_RECEIPT.md); a local run without
PostgreSQL skips marked database tests and is not an equivalent pass.

## Trial D — fictional Email/FileOS together

Use the [cross-source browser walkthrough](CROSS_SOURCE_TRIAL.md) after a locked
install and Docker Desktop setup. It starts its own disposable PostgreSQL 17
container, seeds only fictional Email and file evidence, and opens the loopback
browser. Check the five known-answer queries, citations, separate source layers
and partial coverage. The exact merged code passed hosted CI, but the owner's
interactive Mac acceptance is not recorded yet. Stop with Ctrl-C and verify the
run-specific container is removed; follow the guide if cleanup warns.

## Report a test result

Include the tag or full commit, trial A/B/C/D, operating system and Python version,
exact command, passed/failed/skipped counts, generic error or reason-coded diff,
and whether files were changed. Report unexpected source mutation immediately and
stop. Do not attach real paths, contents, mailbox data, credentials, database dumps
or private logs to a public issue. Record a reproducible synthetic case instead.

## Known limits and next checkpoint

Current FileOS intake is explicit and read-only, not a watcher or FOS-Master
replacement. The donor inventory policy differs in documented cases; several
cloud-placeholder and live-source cases still need independent evaluation.
KnowledgeCore has reviewed assertions and retrieval, not the complete entity,
relationship, project and commitment model. Hosted identity, operations and
provider-neutral LLM client acceptance are pending. The next iteration must
preserve evidence/history, add focused tests first, run exact-head CI and restore,
then merge a reviewed PR and update the changelog/version.
