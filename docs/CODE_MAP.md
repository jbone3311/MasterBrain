# Current MasterBrain code map

Updated 2026-09-21. Existing files, not a proposed directory tree. Python modular
service, vanilla-JavaScript owner UI; no React application or installed RAG framework.
The retained `email_brain` tree is the Email capability. New shared code begins under
`masterbrain` and is not yet wired into Email ingestion.

| Responsibility | Actual files |
|---|---|
| MasterBrain command surface | [cli.py](../src/masterbrain/cli.py); read-only hash/compare/duplicates/FileOS snapshot |
| DataCore contracts | [contracts.py](../src/masterbrain/datacore/contracts.py); immutable source/version/evidence/provenance types |
| Read-only FileOS inventory | [fileos.py](../src/masterbrain/datacore/fileos.py); deterministic bounded snapshot, no source effects |
| Isolated FileOS documents | [document contract](../src/masterbrain/datacore/document_contract.py), [worker](../src/masterbrain/datacore/document_worker.py), [parent](../src/masterbrain/datacore/document_processor.py), [image](../Dockerfile.documents), [guide](FILEOS_DOCUMENT_EXTRACTION.md) |
| FOS live-donor parity | [parity harness](../scripts/datacore_parity.py), [synthetic corpus](../tests/fixtures/datacore_parity/corpus/), [unit contract](../tests/test_datacore_dedup.py), [stress tests](../tests/test_datacore_stress.py) |
| Structured travel/bill memory | [memory.py](../src/email_brain/memory.py), [memory_schema.py](../src/email_brain/memory_schema.py), [memory_extract.py](../src/email_brain/memory_extract.py), [memory.js](../src/email_brain/web/memory.js), [migration 0014](../migrations/0014_structured_memory.sql) |
| Shared DataCore persistence | [persistence.py](../src/masterbrain/datacore/persistence.py), [migration 0015](../migrations/0015_datacore_persistence.sql), [contract](DATACORE_PERSISTENCE.md) |
| Reviewed KnowledgeCore | [knowledge.py](../src/masterbrain/knowledge.py), [knowledge_schema.py](../src/masterbrain/knowledge_schema.py), [migration 0016](../migrations/0016_knowledgecore.sql), [contract](KNOWLEDGECORE.md) |
| Demo/migrate/serve | [cli.py](../src/email_brain/cli.py) |
| REST/request boundary | [api.py](../src/email_brain/api.py), [schemas.py](../src/email_brain/schemas.py) |
| Bootstrap identity | [auth.py](../src/email_brain/auth.py) |
| Configured API identity | [oidc.py](../src/email_brain/oidc.py), [migration 0013](../migrations/0013_external_identities.sql); verifier, administrator mapping and Store transaction rechecks |
| Optional browser session backend | [browser_auth.py](../src/email_brain/browser_auth.py), [browser_routes.py](../src/email_brain/browser_routes.py); fixed code/PKCE, opaque process sessions and Origin/CSRF; owner UI remains next |
| Private browser TLS startup | [browser_operator.py](../src/email_brain/browser_operator.py), [operator tests](../tests/test_browser_operator.py); explicit mode, private certificate/key checks and non-consuming preflight; not public hosting |
| SQL/search/proposals | [store.py](../src/email_brain/store.py) |
| Owner message reader | [message_reader.py](../src/email_brain/message_reader.py), [message_reader.js](../src/email_brain/web/message_reader.js); source/authority verification, inert text and explicit downloads |
| Reviewed rules | [rules/](../src/email_brain/rules/) |
| MIME/attachments | [normalize.py](../src/email_brain/normalize.py), [attachments.py](../src/email_brain/attachments.py), [calendar_attachment.py](../src/email_brain/calendar_attachment.py) |
| Encrypted local objects | [blobs.py](../src/email_brain/blobs.py) |
| Provider reads | [connectors/](../src/email_brain/connectors/) |
| Worker/checkpoints | [sync.py](../src/email_brain/sync.py), [sync_store.py](../src/email_brain/sync_store.py) |
| Bounded read operator | [read_controller.py](../src/email_brain/read_controller.py); `sync-read`, private preflight, exact ingest identity and guarded Fastmail reads |
| Recovery/jobs | [recovery.py](../src/email_brain/recovery.py), [recovery_jobs.py](../src/email_brain/recovery_jobs.py) |
| Approved document jobs/results | [document_jobs.py](../src/email_brain/document_jobs.py), [migration 0012](../migrations/0012_document_jobs.sql); opt-in search/evidence in Store |
| Restricted processor/controller | [mime_sandbox.py](../src/email_brain/mime_sandbox.py), [sandbox_runner.py](../src/email_brain/sandbox_runner.py) |
| Approved-processing operator CLI | [processing_controller.py](../src/email_brain/processing_controller.py) |
| Separate PDF operator CLI | [document_controller.py](../src/email_brain/document_controller.py); shares private file/identity/storage/polling primitives, not MIME jobs |
| Separate restricted PDF reader | [pdf_contract.py](../src/email_brain/pdf_contract.py), [pdf_worker.py](../src/email_brain/pdf_worker.py), [pdf_processor.py](../src/email_brain/pdf_processor.py), [Dockerfile.pdf](../Dockerfile.pdf) |
| Local candidates | [inference.py](../src/email_brain/inference.py), [local_model.py](../src/email_brain/local_model.py) |
| Fictional inbox/file bytes | [synthetic.py](../src/email_brain/synthetic.py), [attachment_samples.py](../tests/attachment_samples.py) |
| Coherent mailbox/manifest/replay | [synthetic_mailbox.py](../src/email_brain/synthetic_mailbox.py), [synthetic_formats.py](../src/email_brain/synthetic_formats.py) |
| Owner UI | [web/](../src/email_brain/web/) |
| PDF owner workflow/search | [document_review.js](../src/email_brain/web/document_review.js); existing API calls, independent document state and text-only evidence |
| Schema upgrades | [migrations/](../migrations/), [migrate.py](../src/email_brain/migrate.py) |
| Checks | [tests/](../tests/), [CI](../.github/workflows/ci.yml) |
| Offline documentation gate | [check_docs.py](../scripts/check_docs.py), [regression tests](../tests/test_check_docs.py); inventory/paths/supported headings, including `.github/` templates |
| Disposable restore | [restore_drill.py](../scripts/restore_drill.py), [workflow](../.github/workflows/restore-drill.yml) |
| Governance bridge | [factory/](../factory/), [AGENTS.md](../AGENTS.md) |

## Trace an operation

Known-answer generation/replay is in [synthetic_mailbox.py](../src/email_brain/synthetic_mailbox.py);
minimal document bytes are authored by [synthetic_formats.py](../src/email_brain/synthetic_formats.py).
The ordinary parser is unchanged. Independent Office readers remain test-only;
pypdf is also in a dedicated optional worker image, not the default API/MIME image.

The executable approved-job entry point is [processing_controller.py](../src/email_brain/processing_controller.py),
wired through `process-jobs` in [cli.py](../src/email_brain/cli.py).
See [configuration and shutdown](PROCESSING_CONTROLLER.md).

- Search: API -> authenticated context -> Store transaction/RLS -> current evidence
  and attachment FTS -> bounded response -> text-only UI.
- Import: adapter -> sync lease -> atomic event/evidence/receipt/checkpoint;
  injected blob storage can retain larger raw MIME.
- Rule: proposal/review -> simulation -> activation -> immutable revision ->
  search-time virtual labels. No provider API call.
- MIME recovery: approval -> durable grant -> separately authorized controller ->
  restricted image -> versioned recovery and fenced atomic job completion.
- PDF document: separate synthetic approval -> document job -> restricted PDF
  processor -> immutable extraction revision -> opt-in document FTS/page evidence.
  The separate `process-documents` command runs the worker. The owner PDF screen
  grants/reviews consent and inspects results; the MIME operator command cannot run it.

## Contract versus code

Unmarked future tables in [DATA_MODEL.md](DATA_MODEL.md) are not migrations; future MCP tools
in [API_MCP_SPEC.md](API_MCP_SPEC.md) are not registered endpoints. `api.py` is the
implemented bounded surface. The [access-token foundation](IDENTITY_AUTH.md) is
executable; complete production login/lifecycle is not supplied by API docs.

Runtime dependencies are in [pyproject.toml](../pyproject.toml), pinned in
[uv.lock](../uv.lock). Prospective OSS recommendations are not installed dependencies.
Factory governs development and is not imported by the runtime.
