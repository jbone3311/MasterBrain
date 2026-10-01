# Current MasterBrain code map

Updated 2026-09-25. Existing files, not a proposed directory tree. Python modular
service, vanilla-JavaScript owner UI; no React application or installed RAG framework.
The retained `email_brain` tree is the Email capability. New shared code begins under
`masterbrain`; an additive bridge can now map selected current Email evidence without
redirecting Email ingestion or search.

| Responsibility | Actual files |
|---|---|
| MasterBrain command surface | [cli.py](../src/masterbrain/cli.py); read-only hash/compare/duplicates/FileOS snapshot and explicit publication |
| DataCore contracts | [contracts.py](../src/masterbrain/datacore/contracts.py); immutable source/version/evidence/provenance types |
| Read-only FileOS inventory | [fileos.py](../src/masterbrain/datacore/fileos.py); deterministic bounded snapshot, no source effects |
| Confined FileOS source reads | [descriptor reader](../src/masterbrain/datacore/confined_files.py), [snapshot](../src/masterbrain/datacore/fileos.py), [text/document extraction](../src/masterbrain/datacore/extraction.py), [adversarial tests](../tests/test_fileos_confined_reads.py), [ADR-100](adr/100_confined_fileos_reads.md); integrated via PR #28; hosted gate/restore green on `6e2eb8e` |
| Extracted FileOS inventory classifier | [fileos_junk_filter.py](../src/masterbrain/datacore/fileos_junk_filter.py); [3,000-path donor parity](../scripts/fileos_junk_parity.py), [contract](FILEOS_JUNK_POLICY.md); not yet integrated into snapshots |
| Synthetic FileOS whole-inventory shadow | [comparator](../scripts/fileos_inventory_shadow.py), [tests](../tests/test_fileos_inventory_shadow.py), [contract](FILEOS_INVENTORY_SHADOW.md), [ADR-093](adr/093_fileos_inventory_shadow.md); no runtime publication |
| Nonpublishing FOS policy shadow | [scanner](../src/masterbrain/datacore/fileos_donor_shadow.py), [descriptor metadata stat](../src/masterbrain/datacore/confined_files.py), [pinned-donor comparator](../scripts/fileos_donor_policy_shadow.py), [tests](../tests/test_fileos_donor_policy_shadow.py), [ADR-111](adr/111_fileos_donor_policy_shadow.md); no snapshot or publication switch |
| Nonpublishing donor candidate ledger | [builder](../src/masterbrain/datacore/fileos_donor_candidate.py), [contract](FILEOS_DONOR_CANDIDATE.md), [tests](../tests/test_fileos_donor_candidate.py), [ADR-112](adr/112_fileos_donor_candidate_ledger.md); v1 importer refuses it |
| Read-only v1-to-donor policy preview | [comparison and completed-run wrapper](../src/masterbrain/datacore/fileos_donor_transition.py), [database verifier](../src/masterbrain/datacore/persistence.py), [contract](FILEOS_DONOR_TRANSITION.md), [unit tests](../tests/test_fileos_donor_transition.py), [PostgreSQL tests](../tests/test_postgres.py), [ADR-113](adr/113_fileos_policy_transition_preview.md) and [ADR-114](adr/114_completed_fileos_baseline_preview.md); no absence or publication |
| FileOS completion coverage gate | [DataCore validation](../src/masterbrain/datacore/persistence.py), [private publisher preflight](../src/masterbrain/fileos_controller.py), [unit tests](../tests/test_fileos_completion_coverage.py), [PostgreSQL tests](../tests/test_postgres.py), [ADR-094](adr/094_fileos_completion_coverage.md) |
| FileOS mass-loss completion guard | [DataCore completion](../src/masterbrain/datacore/persistence.py), [threshold tests](../tests/test_fileos_completion_coverage.py), [PostgreSQL regression](../tests/test_postgres.py), [ADR-095](adr/095_fileos_mass_loss_guard.md) |
| FileOS inventory-policy identity | [versioned snapshot](../src/masterbrain/datacore/fileos.py), [DataCore completion](../src/masterbrain/datacore/persistence.py), [migration 0031](../migrations/0031_fileos_policy_identity.sql), [unit tests](../tests/test_fileos_completion_coverage.py), [PostgreSQL regression](../tests/test_postgres.py), [populated upgrade](../tests/test_recovery.py), [restore seed](../scripts/restore_drill.py), [ADR-096](adr/096_fileos_inventory_policy_identity.md) |
| FileOS exclusion/skip ledger | [snapshot](../src/masterbrain/datacore/fileos.py), [completion guard](../src/masterbrain/datacore/persistence.py), [unit tests](../tests/test_fileos_completion_coverage.py), [PostgreSQL regression](../tests/test_postgres.py), [ADR-097](adr/097_fileos_exclusion_ledger.md) |
| FileOS physical-root binding | [snapshot](../src/masterbrain/datacore/fileos.py), [controller](../src/masterbrain/fileos_controller.py), [adapter](../src/masterbrain/datacore/extraction.py), [DataCore](../src/masterbrain/datacore/persistence.py), [migration 0032](../migrations/0032_fileos_root_binding.sql), [tests](../tests/test_fileos_completion_coverage.py), [ADR-098](adr/098_fileos_root_binding.md) |
| Isolated FileOS documents | [document contract](../src/masterbrain/datacore/document_contract.py), [worker](../src/masterbrain/datacore/document_worker.py), [parent](../src/masterbrain/datacore/document_processor.py), [image](../Dockerfile.documents), [guide](FILEOS_DOCUMENT_EXTRACTION.md) |
| Isolated FileOS archive inventory | [contract](../src/masterbrain/datacore/archive_contract.py), [worker](../src/masterbrain/datacore/archive_worker.py), [parent](../src/masterbrain/datacore/archive_processor.py), [image](../Dockerfile.archives), [live donor parity](../scripts/archive_parity.py), [guide](FILEOS_ARCHIVE_EXTRACTION.md) |
| Archive hash-manifest persistence | [DataCore store](../src/masterbrain/datacore/persistence.py), [migration 0023](../migrations/0023_archive_manifests.sql), [contract](ARCHIVE_MANIFEST_PERSISTENCE.md) |
| Archive ledger and parent integrity | [migration 0033](../migrations/0033_archive_ledger_parent_integrity.sql), [PostgreSQL regressions](../tests/test_postgres.py), [populated upgrade](../tests/test_recovery.py), [ADR-099](adr/099_archive_ledger_and_parent_integrity.md); integrated via PR #28; hosted CI/restore green |
| Hash-bound archive member read | [contract](../src/masterbrain/datacore/archive_member_contract.py), [worker](../src/masterbrain/datacore/archive_member_worker.py), [parent](../src/masterbrain/datacore/archive_member_processor.py), [root revalidation](../src/masterbrain/datacore/archive_member.py), [guide](ARCHIVE_MEMBER_READ.md) |
| Archive member text derivative | [orchestration](../src/masterbrain/datacore/archive_member_text.py), [DataCore store](../src/masterbrain/datacore/persistence.py), [migration 0024](../migrations/0024_archive_member_text_derivatives.sql), [contract](ARCHIVE_MEMBER_TEXT.md) |
| Private archive-member text operator | [archive_member_controller.py](../src/masterbrain/archive_member_controller.py), [CLI](../src/masterbrain/cli.py), [contract](ARCHIVE_MEMBER_OPERATOR.md), [ADR-079](adr/079_private_archive_member_text_operator.md) |
| Current archive-derivative search | [DataCore query](../src/masterbrain/datacore/persistence.py), [Brain API](../src/email_brain/api.py), [migration 0025](../migrations/0025_current_archive_derivative_search.sql), [contract](ARCHIVE_DERIVATIVE_SEARCH.md) |
| Private archive-member preview | [archive controller](../src/masterbrain/archive_member_controller.py), [DataCore query](../src/masterbrain/datacore/persistence.py), [CLI](../src/masterbrain/cli.py), [contract](ARCHIVE_MEMBER_PREVIEW.md) |
| Sealed archive-member text batch | [archive controller](../src/masterbrain/archive_member_controller.py), [CLI](../src/masterbrain/cli.py), [contract](ARCHIVE_MEMBER_BATCH.md), [ADR-082](adr/082_sealed_archive_member_batch.md) |
| Archive-member PDF/Office derivative | [two-worker orchestration](../src/masterbrain/datacore/archive_member_document.py), [archive/document controller](../src/masterbrain/archive_member_controller.py), [DataCore store](../src/masterbrain/datacore/persistence.py), [migration 0026](../migrations/0026_archive_member_documents.sql), [contract](ARCHIVE_MEMBER_DOCUMENT.md), [ADR-083](adr/083_archive_member_documents.md) |
| Current archive-document search | [DataCore query](../src/masterbrain/datacore/persistence.py), [Brain API](../src/email_brain/api.py), [migration 0027](../migrations/0027_current_archive_document_search.sql), [contract](ARCHIVE_DOCUMENT_SEARCH.md), [ADR-084](adr/084_current_archive_document_search.md) |
| Private archive-document preview | [archive controller](../src/masterbrain/archive_member_controller.py), [DataCore query](../src/masterbrain/datacore/persistence.py), [CLI](../src/masterbrain/cli.py), [contract](ARCHIVE_DOCUMENT_PREVIEW.md), [ADR-085](adr/085_private_archive_document_preview.md) |
| Sealed archive-document batch | [archive controller and plan schema](../src/masterbrain/archive_member_controller.py), [CLI](../src/masterbrain/cli.py), [contract](ARCHIVE_DOCUMENT_BATCH.md), [ADR-086](adr/086_sealed_archive_document_batch.md) |
| Isolated image OCR worker | [closed contract](../src/masterbrain/datacore/image_ocr_contract.py), [worker](../src/masterbrain/datacore/image_ocr_worker.py), [parent](../src/masterbrain/datacore/image_ocr_processor.py), [image](../Dockerfile.images), [live donor parity](../scripts/image_ocr_parity.py), [contract](ARCHIVE_IMAGE_OCR.md), [ADR-087](adr/087_archive_image_ocr_boundary.md) |
| Archive-member image OCR composition and persistence | [two-worker orchestration/publication guard](../src/masterbrain/datacore/archive_member_image_ocr.py), [DataCore transaction](../src/masterbrain/datacore/persistence.py), [migration 0028](../migrations/0028_archive_member_image_ocr.sql), [composition contract](ARCHIVE_MEMBER_IMAGE_OCR.md), [persistence contract](ARCHIVE_MEMBER_IMAGE_PERSISTENCE.md), [ADR-088](adr/088_archive_member_image_ocr.md), [ADR-089](adr/089_archive_member_image_persistence.md) |
| Private archive-image OCR operator | [archive controller](../src/masterbrain/archive_member_controller.py), [CLI](../src/masterbrain/cli.py), [operator contract](ARCHIVE_MEMBER_IMAGE_OPERATOR.md), [ADR-090](adr/090_private_archive_image_operator.md); hosted acceptance green |
| Current archive-image OCR search | [DataCore query](../src/masterbrain/datacore/persistence.py), [Brain API](../src/email_brain/api.py), [migration 0036](../migrations/0036_current_archive_image_search.sql), [contract](ARCHIVE_IMAGE_SEARCH.md), [ADR-107](adr/107_current_archive_image_search.md); separate current-only layer |
| Authenticated FileOS operator | [fileos_controller.py](../src/masterbrain/fileos_controller.py), [ADR-054](adr/054_fileos_operator_publication.md) |
| FileOS index generation operator | [fileos_index_controller.py](../src/masterbrain/fileos_index_controller.py), [ADR-059](adr/059_fileos_index_operator.md) |
| Email message/attachment/document bridge operator | [email_bridge_controller.py](../src/masterbrain/email_bridge_controller.py), [ADR-063](adr/063_email_bridge_operator.md), [ADR-067](adr/067_email_part_bridge_operator.md) |
| FOS live-donor parity | [parity harness](../scripts/datacore_parity.py), [synthetic corpus](../tests/fixtures/datacore_parity/corpus/), [unit contract](../tests/test_datacore_dedup.py), [stress tests](../tests/test_datacore_stress.py) |
| Structured travel/bill memory | [memory.py](../src/email_brain/memory.py), [memory_schema.py](../src/email_brain/memory_schema.py), [memory_extract.py](../src/email_brain/memory_extract.py), [memory.js](../src/email_brain/web/memory.js), [migration 0014](../migrations/0014_structured_memory.sql) |
| Shared DataCore persistence | [persistence.py](../src/masterbrain/datacore/persistence.py), [migration 0015](../migrations/0015_datacore_persistence.sql), [run receipts 0017](../migrations/0017_fileos_run_receipts.sql), [inventory reconciliation 0018](../migrations/0018_fileos_inventory_reconciliation.sql), [index generations 0019](../migrations/0019_datacore_index_generations.sql), [Email bridge 0020](../migrations/0020_email_datacore_bridge.sql), [attachment bridge 0021](../migrations/0021_email_attachment_bridge.sql), [approved-PDF derivative bridge 0022](../migrations/0022_email_document_extraction_bridge.sql), [contract](DATACORE_PERSISTENCE.md) |
| Reviewed KnowledgeCore | [knowledge.py](../src/masterbrain/knowledge.py), [knowledge_schema.py](../src/masterbrain/knowledge_schema.py), [migration 0016](../migrations/0016_knowledgecore.sql), [contract](KNOWLEDGECORE.md) |
| Fictional cross-source browser trial | [launcher](../tests/cross_source_preview.py), [known-answer/tenant tests](../tests/test_cross_source_preview.py), [browser script](../tests/cross_source_assets/trial.js), [guide](CROSS_SOURCE_TRIAL.md); local PostgreSQL/Docker and fictional data only |
| Privacy-safe API failure correlation | [request boundary](../src/email_brain/api.py), [failure tests](../tests/test_request_failure_logging.py), [ADR-104](adr/104_privacy_safe_error_observability.md); production log collection remains open |
| Current callable-function summary | [CURRENT_FUNCTIONS.md](CURRENT_FUNCTIONS.md); this code map lists owners, not release acceptance |
| Demo/migrate/serve | [cli.py](../src/email_brain/cli.py) |
| REST/request boundary | [api.py](../src/email_brain/api.py), [schemas.py](../src/email_brain/schemas.py) |
| Bootstrap identity | [auth.py](../src/email_brain/auth.py) |
| Configured API identity | [oidc.py](../src/email_brain/oidc.py), [migration 0013](../migrations/0013_external_identities.sql), [migration 0034](../migrations/0034_identity_admin_enrollment.sql), [migration 0035](../migrations/0035_identity_resolver.sql); verifier, exact runtime resolver, least-privilege administrator mapping and Store transaction rechecks |
| Opt-in tenant database-login fence | [migration 0037](../migrations/0037_tenant_login_fence.sql), [DBA provisioning helper](../src/email_brain/migrate.py), [adversarial PostgreSQL test](../tests/test_postgres.py), [contract](TENANT_LOGIN_FENCE.md), [ADR-108](adr/108_tenant_login_rls_fence.md); not a hosted multi-tenant release |
| Opt-in tenant-routed API service | [private route file](../src/email_brain/tenant_db.py), [Store routing](../src/email_brain/store.py), [compatibility CLI](../src/email_brain/cli.py), [real PostgreSQL/API test](../tests/test_postgres.py), [private-file tests](../tests/test_tenant_db.py), [ADR-109](adr/109_tenant_database_routing.md); private workers and hosted operations remain separate |
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
| Protected-record TRUNCATE refusal | [migration 0030](../migrations/0030_protected_record_truncate_guards.sql), [contract](EVIDENCE_TRUNCATE_GUARDS.md), [ADR-092](adr/092_protected_record_truncate_guards.md) |
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
