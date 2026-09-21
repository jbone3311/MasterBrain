# Current code map

Updated 2026-09-20. Existing files, not a proposed directory tree. Python modular
service, vanilla-JavaScript owner UI; no React application or installed RAG framework.

| Responsibility | Actual files |
|---|---|
| Demo/migrate/serve | [cli.py](../src/email_brain/cli.py) |
| REST/request boundary | [api.py](../src/email_brain/api.py), [schemas.py](../src/email_brain/schemas.py) |
| Bootstrap identity | [auth.py](../src/email_brain/auth.py) |
| SQL/search/proposals | [store.py](../src/email_brain/store.py) |
| Reviewed rules | [rules/](../src/email_brain/rules/) |
| MIME/attachments | [normalize.py](../src/email_brain/normalize.py), [attachments.py](../src/email_brain/attachments.py), [calendar_attachment.py](../src/email_brain/calendar_attachment.py) |
| Encrypted local objects | [blobs.py](../src/email_brain/blobs.py) |
| Provider reads | [connectors/](../src/email_brain/connectors/) |
| Worker/checkpoints | [sync.py](../src/email_brain/sync.py), [sync_store.py](../src/email_brain/sync_store.py) |
| Recovery/jobs | [recovery.py](../src/email_brain/recovery.py), [recovery_jobs.py](../src/email_brain/recovery_jobs.py) |
| Restricted processor/controller | [mime_sandbox.py](../src/email_brain/mime_sandbox.py), [sandbox_runner.py](../src/email_brain/sandbox_runner.py) |
| Local candidates | [inference.py](../src/email_brain/inference.py), [local_model.py](../src/email_brain/local_model.py) |
| Fictional inbox/file bytes | [synthetic.py](../src/email_brain/synthetic.py), [attachment_samples.py](../tests/attachment_samples.py) |
| Owner UI | [web/](../src/email_brain/web/) |
| Schema upgrades | [migrations/](../migrations/), [migrate.py](../src/email_brain/migrate.py) |
| Checks | [tests/](../tests/), [CI](../.github/workflows/ci.yml) |
| Disposable restore | [restore_drill.py](../scripts/restore_drill.py), [workflow](../.github/workflows/restore-drill.yml) |
| Governance bridge | [factory/](../factory/), [AGENTS.md](../AGENTS.md) |

## Trace an operation

- Search: API -> authenticated context -> Store transaction/RLS -> current evidence
  and attachment FTS -> bounded response -> text-only UI.
- Import: adapter -> sync lease -> atomic event/evidence/receipt/checkpoint;
  injected blob storage can retain larger raw MIME.
- Rule: proposal/review -> simulation -> activation -> immutable revision ->
  search-time virtual labels. No provider API call.
- Processing: approval -> durable grant -> separately authorized controller ->
  restricted image -> versioned recovery and fenced atomic job completion.

## Contract versus code

Future tables in [DATA_MODEL.md](DATA_MODEL.md) are not migrations; future MCP tools
in [API_MCP_SPEC.md](API_MCP_SPEC.md) are not registered endpoints. `api.py` is the
implemented bootstrap surface. Production identity is not supplied by API docs.

Runtime dependencies are in [pyproject.toml](../pyproject.toml), pinned in
[uv.lock](../uv.lock). Prospective OSS recommendations are not installed dependencies.
Factory governs development and is not imported by the runtime.
