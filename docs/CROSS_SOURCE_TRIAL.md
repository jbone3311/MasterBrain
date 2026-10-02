# Try MasterBrain: email and file search together

This is a real PostgreSQL-backed, fictional-data trial. It does not connect your
mail accounts or scan personal folders. No real token is needed.

## Start on your Mac

Prerequisites: a checkout of this repository, `uv`, and either Docker Desktop
running or local PostgreSQL 17 (`initdb` and `pg_ctl` on `PATH`). Use a supported
Python 3.13 or 3.14 environment. From the repository:

```sh
uv sync --locked --extra dev --python '>=3.13,<3.15' --no-editable
uv run --no-sync python tests/cross_source_preview.py --synthetic-preview
```

Alternatively double-click `Start-MasterBrain-Trial.command` in the checkout.
The launcher uses the same locked non-editable installation and suppresses a
second automatic sync when it starts Python. This avoids relying on an editable
`.pth` file that some macOS environments mark hidden; it does not change the
normal developer installation workflow.
The launcher creates an isolated temporary PostgreSQL 17 container when Docker
is available, otherwise a new private temporary PostgreSQL 17 cluster. You can
choose explicitly with `--backend docker` or `--backend local`. It never connects
to an existing database. Docker may need to download the PostgreSQL image on
the first run. The browser opens at `http://127.0.0.1:8766/trial`. The initial
tab receives a random read-only trial credential automatically. Leave the
terminal running while testing. No hosted
server, LLM subscription, API key or real mailbox configuration is involved.

The browser credential expires after two hours and is not saved. Reloading the
page or manually opening the address loses it: stop and restart the launcher to
open a new authenticated tab. Do not enter a real token. A port conflict can be
resolved with `--port 8767`; binding remains loopback-only.

To try the first-party read-only question workspace against the same fictional
data, keep the launcher running, open `http://127.0.0.1:8766/brain`, and paste
the temporary trial credential from the URL printed in the launcher's terminal
into its access field. The trial page removes that fragment from its own URL;
the `/brain` workspace never reads a URL fragment or stores the credential.
Ask on this screen selects bounded, exact source quotes locally and opens
supporting evidence. It also lists reviewed KnowledgeCore matches separately;
those are interpretations, not exact quotations. Search only shows grouped current results. Neither path
generates an AI-written answer or changes files/email. Use the launcher's actual port if
you selected a nondefault one.

For a question-shaped check, Ask “Find the insurance certificate for Cedar
Harbor.” It should return verified Email and FileOS quotes containing
“insurance.” Search only with that entire sentence is literal lexical search
and may show no results; search for “insurance” to see the grouped records.
Ask removes only fixed question boilerplate, not synonyms or temporal intent.
Then Ask “readiness.” It should show no exact source quote and one fictional
reviewed commitment linked to both an Email and a File. The commitment is a
human-reviewed interpretation; opening either link shows underlying evidence.
Then Ask “When is Maple Arcade closing?” It should show two exact, conflicting
source quotes: the file says November 12, 2026 and the Email says November 19,
2026. MasterBrain does not decide which date is correct; the generic answer
text is not a resolution. This is a deliberate evaluation case, not current
project advice.

## Known answers

| Search | Email | Files | Reviewed knowledge | What to inspect |
|---|---:|---:|---:|---|
| Cedar Harbor | 2 | 2 | 0 | All indexed evidence for the fictional deal |
| insurance | 1 | 1 | 0 | Email and checklist both say the certificate is outstanding |
| appraisal | 1 | 1 | 0 | Email and checklist both say the appraisal was received |
| Juniper Plaza | 1 | 1 | 0 | A separate fictional project, not Cedar Harbor |
| Maple Arcade | 1 | 1 | 0 | Conflicting fictional closing dates; inspect both sources |
| readiness | 0 | 0 | 1 | Reviewed closing follow-up, with two source links; not an exact source quote |
| nonexistentcanary | 0 | 0 | 0 | Empty results; no invented answer |

Open evidence on an Email result and on a File result. The separately authorized
content read should show the supporting source text directly, while the expandable citation
section shows its immutable identity/provenance. The term sheet proposes a fictional
$8,000,000 loan and a 1.25 debt-service coverage ratio; the checklist lists October
15, 2026 as a fictional target closing. These are source statements, not advice.

Open source coverage/freshness. The response intentionally says coverage is partial:
only explicitly bridged current email and activated FileOS generations count.
The synthetic source observation date is September 24, 2026. One reviewed
KnowledgeCore commitment is populated; archive layers are not. Ranks are not
compared across layers.

## Stop and report

Press Ctrl-C in the terminal. Docker mode verifies its run-specific container
marker before removal. Local mode stops only its new temporary cluster before
removing its data directory. Temporary fictional files are also removed.
If Docker cleanup fails, the terminal names the container to check manually.
If local stop cannot be confirmed, it preserves the exact synthetic cluster
directory and prints its path for inspection. No existing container, database
or source folder is deleted. After a forced termination, inspect only this
run's named `masterbrain-trial-*` container or `masterbrain-trial-pg-*` directory
before manual cleanup. Do not remove a local directory while its server runs.

Report the full Git commit, operating system, Python version, query, expected vs.
actual counts and any visible generic error. Include only fictional screenshots.
Do not attach personal documents, credentials, database dumps or private logs.

## Automated checks and limitations

The same seed helper runs through the real Brain API in
`tests/test_cross_source_preview.py`. To verify the actual local launcher
without a browser, run:

```sh
bash Start-MasterBrain-Trial.command --backend local --self-test
```

With the existing disposable PostgreSQL test environment configured, run:

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
[strict runtime](STRICT_RUNTIME.md), [ADR-103](adr/103_synthetic_cross_source_trial.md)
and [ADR-137](adr/137_local_disposable_postgres_trial.md).
