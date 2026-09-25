# Try MasterBrain: email and file search together

This is a real PostgreSQL-backed, fictional-data trial. It does not connect your
mail accounts or scan personal folders. No real token is needed.

## Start on your Mac

Prerequisites: a checkout of this repository, `uv`, and Docker Desktop installed
and running. Use a current patched Python 3.12 environment. From the repository:

```sh
uv sync --locked --extra dev --python 3.12
uv run python tests/cross_source_preview.py --synthetic-preview
```

Alternatively double-click `Start-MasterBrain-Trial.command` in the checkout.
The launcher creates an isolated temporary PostgreSQL container and opens your
browser at `http://127.0.0.1:8766/trial`. It may need to download the PostgreSQL
image on the first run. The initial tab receives a random read-only trial
credential automatically. Leave the terminal running while testing. No hosted
server, LLM subscription, API key or real mailbox configuration is involved.

The browser credential expires after two hours and is not saved. Reloading the
page or manually opening the address loses it: stop and restart the launcher to
open a new authenticated tab. Do not enter a real token. A port conflict can be
resolved with `--port 8767`; binding remains loopback-only.

## Known answers

| Search | Expected Email results | Expected File results | What to inspect |
|---|---:|---:|---|
| Cedar Harbor | 2 | 2 | All indexed evidence for the fictional deal |
| insurance | 1 | 1 | Email and checklist both say the certificate is outstanding |
| appraisal | 1 | 1 | Email and checklist both say the appraisal was received |
| Juniper Plaza | 1 | 1 | A separate fictional project, not Cedar Harbor |
| nonexistentcanary | 0 | 0 | Empty results; no invented answer |

Open evidence on an Email result and on a File result. The separately authorized
content read should show the supporting source text, while the expandable citation
section shows its immutable identity/provenance. The term sheet proposes a fictional
$8,000,000 loan and a 1.25 debt-service coverage ratio; the checklist lists October
15, 2026 as a fictional target closing. These are source statements, not advice.

Open source coverage/freshness. The response intentionally says coverage is partial:
only explicitly bridged current email and activated FileOS generations count.
The synthetic source observation date is September 24, 2026. Knowledge and archive
layers are not populated in this walkthrough. Ranks are not compared across layers.

## Stop and report

Press Ctrl-C in the terminal. The launcher verifies its run-specific container
marker before removing that container; temporary fictional files are also removed.
If verification or Docker cleanup fails, the terminal names the trial container to
check manually. No existing Docker container, database or source folder is deleted.
After a forced termination, remove only the `masterbrain-trial-*` container created
for this run through Docker Desktop. It has no persistent source-volume mount.

Report the full Git commit, operating system, Python version, query, expected vs.
actual counts and any visible generic error. Include only fictional screenshots.
Do not attach personal documents, credentials, database dumps or private logs.

## Automated checks and limitations

The same seed helper runs through the real Brain API in
`tests/test_cross_source_preview.py`. With the existing disposable PostgreSQL test
environment configured, run:

```sh
uv run pytest -q tests/test_cross_source_preview.py
```

The tests check known answers, cited bounded content, freshness/coverage, source
hash preservation, two nonempty tenants and authorization. Without PostgreSQL,
marked database tests skip locally; that is not full acceptance. Hosted CI supplies
PostgreSQL and requires them. A passed API/static suite is not a claim that the
interactive browser was tested on your Mac.

This is a synthetic alpha, not a deployed product or FileOS replacement. There is
no live synchronization, automatic reasoning, sending, moving, deleting, upload,
production identity or donor cutover. See [alpha testing](ALPHA_TESTING.md),
[strict runtime](STRICT_RUNTIME.md) and [ADR-103](adr/103_synthetic_cross_source_trial.md).
