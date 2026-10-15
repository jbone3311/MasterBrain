# Run the synthetic prototype

Requirements: Python 3.11+, `uv`, and PostgreSQL 17 (local installation or Docker).
No real mail, cloud account, provider token, or model is needed. The included
`compose.yaml` starts only PostgreSQL, on loopback, with a named Docker volume.
The authoring Mac also has local PostgreSQL 17.11; the combined synthetic demo
was exercised against a disposable database. This does not establish hosted
or live-source readiness.

## Keep runtime state off Dropbox

For fake-issuer development of the separate API identity mode, follow
[IDENTITY_AUTH.md](IDENTITY_AUTH.md). `serve --oidc-config` requires migration 0013,
private configuration and existing administrator-managed mappings; it rejects
simultaneous bootstrap credentials and stays loopback-only. Unit tests generate
keys and intercept every issuer request; no real registration is needed or implied.

Use a private directory such as `~/Library/Application Support/MasterBrain`.
Keep secrets, credential files and local environments outside the synced checkout.
For a Dropbox checkout, set `UV_PROJECT_ENVIRONMENT` to an absolute path outside
Dropbox before `uv sync`. A normal non-synced checkout may use ignored `.venv`.

## Configuration and start

Create an owner-readable-only environment file outside Git/Dropbox with your
password manager/editor. `.env.example` lists variable names, not working secrets.
Use separate random administrator/runtime passwords. Percent-encode reserved
password characters in URLs. Never paste actual DSNs/tokens into issues or logs.

- `EMAIL_BRAIN_ADMIN_DSN`: schema/provisioning only; must be able to create roles.
- `EMAIL_BRAIN_DSN`: `email_brain_runtime`, never owner/superuser.
- `EMAIL_BRAIN_RUNTIME_PASSWORD`: at least 24 random characters; init only.
- `EMAIL_BRAIN_CREDENTIALS_FILE`: generated digest registry, mode 0600.
- `EMAIL_BRAIN_POSTGRES_PASSWORD`: Compose database administrator password.

Load these variables privately, then from the checkout:

```sh
uv sync --locked --extra dev
docker compose up -d postgres
uv run email-brain migrate
uv run email-brain init-demo --state-dir "~/Library/Application Support/MasterBrain"
uv run email-brain seed-demo --state-dir "~/Library/Application Support/MasterBrain"
uv run email-brain serve
```

For a **new, disposable combined-source MasterBrain demo**, use the branded
entry point with the same private environment variables on a fresh database:

```sh
uv run masterbrain demo migrate
uv run masterbrain demo init --state-dir "~/Library/Application Support/MasterBrain"
uv run masterbrain demo seed --state-dir "~/Library/Application Support/MasterBrain"
uv run masterbrain demo serve
```

Use a fresh database/cluster: initialization deliberately refuses an existing
`email_brain_runtime` role or credential files. The new seed imports three
fictional emails, bridges their current versions into DataCore, snapshots one
generated fictional text file under the private state directory, publishes its
text, and creates one explicitly synthetic reviewed project citing both source
occurrences. The seed also records a complete fictional FileOS run and activates
its immutable search generation, so both sources appear in the **current**
Brain search rather than only the older combined search. It prints the project
ID. Search `fictional` at `/brain` to see Email and FileOS results, or open the
project dossier through the Brain API. Its Markdown can be inspected by the
owner's review-scoped API, but inspection only verifies cited quote previews;
it does not automatically publish imported assertions. Running the seed again
is idempotent. The underlying `email-brain`
`init-masterbrain-demo`/`seed-masterbrain-demo` aliases remain for compatibility.
The owner token has Brain/Knowledge read
and Knowledge review scopes but no worker or file-effect scopes. The older
Email-only demo remains unchanged. Neither demo uses a real source or safely
enrolls a real assistant. Do not reuse the disposable fixture database as a
private pilot; follow the separate enrollment and restore gates first.

`init-demo` creates a synthetic tenant/account and least-privileged runtime role;
it refuses existing roles/credentials rather than replacing them. Privately read
the generated `owner-token.txt` and paste it into `http://127.0.0.1:8080/`. It expires
after seven days; the page stores it only in memory. Search `Melron`, inspect a
citation, propose a project, and review it. Approval deliberately applies nothing.

ADR-036 fixes demo registry generation to include only explicit human scopes;
neither processing-worker scope belongs in an owner credential. The emitted
registry is validated before saving. Do not rerun `init-demo` over an existing
installation to repair credentials: it deliberately refuses existing roles/files.
Inspect any earlier failed setup privately; do not discard its retained state.

Unset `EMAIL_BRAIN_ADMIN_DSN` and `EMAIL_BRAIN_RUNTIME_PASSWORD` before launching
the long-lived API process. Do not expose bootstrap authentication through a
public tunnel or reverse proxy. It is not production identity management.

## Tests

For separate approved-job execution, follow [PROCESSING_CONTROLLER.md](PROCESSING_CONTROLLER.md).
The demo human token cannot act as a worker. Use explicit private worker credentials,
an approved image and `process-jobs --check` before a bounded synthetic run. The
command does not contact providers, generate approvals or install a background service.

For PDFs, use the separate [document controller guide](DOCUMENT_CONTROLLER.md):
`process-documents`, exact document-worker scope and fixed synthetic policy. The
existing document approval API can be explicitly configured with
`serve --document-processor-version`; the [owner PDF screen](DOCUMENT_REVIEW_SCREEN.md)
now exposes separate selection/approval/history/cancellation and cited page results.
Worker execution is still a separate explicit command, not a browser operation.

For a larger fictional inbox, use this **instead of** `seed-demo` on a fresh
initialized synthetic account:

```sh
uv run email-brain seed-corpus --state-dir "~/Library/Application Support/MasterBrain" --count 256
```

Includes projects, receipts, meetings, newsletters, multilingual mail, untrusted
instruction text, HTML alternatives and CSV/PDF attachments. PDFs are deferred,
not claimed extracted. Search `marker00007`, `Melron`, or `Synthetic` in the UI.
The importer resumes from its committed page after interruption; rerunning with
the same count is a no-op once complete. Different corpus counts and unrelated
account cursors are refused. Limit: 10,000 generated emails. Only the configured
database is contacted; no mailbox or model calls. This is fixture data, not a
substitute for a calibrated real-email evaluation set.

```sh
uv run ruff check .
uv run mypy src
uv run pytest -q
node --test tests/web_session.test.cjs tests/web_processing.test.cjs tests/web_documents.test.cjs
node --test tests/web_reader.test.cjs
uv run python scripts/deployment_gate.py
uv run python scripts/check_docs.py
```

For PostgreSQL tests create a **disposable** database named `email_brain_test*`
and set `EMAIL_BRAIN_TEST_ADMIN_DSN`. Tests create synthetic rows/random runtime
roles; they do not erase databases. Never use production. CI refuses silent skips.
The UI contract harness uses Node's standard test runner (Node 20+), with no npm
dependencies. It is not a real browser/accessibility suite. The owner page also
supports import health and held-message metadata review from a search result's
account button. Human owners with review/evidence scopes can explicitly retry one
held receipt using the displayed parser version. See [recovery](QUARANTINE_RECOVERY.md).
That quarantine screen exposes no raw download or mailbox effect. The separate
[owner reader](MESSAGE_READER.md) now allows explicit verified original/leaf-part
exports. [User testing](USER_TESTING.md) also provides a fictional preview requiring
no local database; it is not a substitute for this real SQL workflow.

The owner screen also exposes [processing history/approval/cancellation](PROCESSING_REVIEW_SCREEN.md).
The default server does not automatically configure an isolated parser/controller;
history is distinct from worker liveness. The separately documented visual fixture
can preview controls without PostgreSQL, but simulates jobs and proves no durability.
The [test mailbox guide](TEST_MAILBOX_PLAN.md) now documents `export-test-mailbox`
and `seed-test-mailbox`: coherent scenarios, actual attachments, known-answer
manifests and bounded optional pacing/resume. Use a fresh synthetic account;
there is no SMTP delivery or automatically installed continuous service.

Stop the API with Ctrl-C; `docker compose stop` preserves the database. Do not use
`down -v` unless intentionally deleting that local volume. Migrations are
checksum-verified and forward-only; never edit an applied migration. If provisioning
fails partway, inspect the explicit created role/tenant/private files before retrying.
The CLI suppresses sensitive DB exception details; diagnose in a private admin session.

No live provider scheduler, default binary extraction, general raw-object tool, SMTP, MCP transport,
real model, purge job or invitation flow is active. See [status](IMPLEMENTATION_STATUS.md)
and [backlog](BACKLOG.md). The Dockerfile is a developer image; pin image digests,
scan it and test least privilege before promotion.
