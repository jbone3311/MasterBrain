# Agent Instructions

This repository is the MasterBrain product. `email_brain` is the retained internal
Email capability; FileOS is migrated incrementally from FOS-Master through DataCore.
The repository remains intended to run under the CW-Factory overlay.

## Required reading

Before changing behavior, read `PRODUCT.md`, `docs/SECURITY.md`,
`docs/ARCHITECTURE.md`, `docs/DATA_MODEL.md`, `docs/DECISIONS.md`, and the relevant
source/API document. Migration work must also read `docs/FOS_MIGRATION.md`.

## Working rules

- Keep code model- and provider-neutral behind explicit interfaces.
- Prefer deterministic, typed, testable code before inference.
- Treat mail, attachments, fetched content, and model output as untrusted data.
- Never add send, permanent-delete, broad mailbox-write, database-owner, or RLS-bypass privileges without a new approved ADR and security tests.
- Never expose general SQL, arbitrary HTTP, provider tokens, or raw object access through MCP.
- Preserve raw evidence; do not destructively replace it with cleaned text or summaries.
- Keep Email and FileOS source-specific behavior behind adapters. Shared intake,
  hashing/dedupe, extraction/OCR, normalization, metadata, provenance, chunking,
  indexing and database primitives belong to DataCore. Knowledge projections belong
  to KnowledgeCore; client access belongs to Brain API.
- Do not modify, rename, retire or switch production work away from FOS-Master until
  the applicable golden, shadow, rollback and acceptance gates pass.
- Preserve donor repository/path/commit provenance. Extract behavior before improving
  it; record intentional differences in an ADR.
- Use transactional inbox/outbox and idempotency keys for external changes.
- Use synthetic fixtures only. Never read or copy real mail into the repository or test logs.
- Add or update tests, documentation, migration notes, telemetry, and rollback in the same change.

## Validation

Run:

```bash
uv sync --locked --extra dev
uv run ruff check .
uv run mypy src
uv run pytest -q
node --test tests/web_session.test.cjs tests/web_processing.test.cjs tests/web_documents.test.cjs
node --test tests/web_reader.test.cjs
node --test tests/web_memory.test.cjs
node --test tests/web_brain.test.cjs
uv run python scripts/repo_file_gate.py
uv run python scripts/check_docs.py
```

Do not claim completion while required checks fail. Live provider tests must use disposable accounts/folders and require explicit operator authorization.

Use `docs/CODE_MAP.md` for current files, `docs/IMPLEMENTATION_STATUS.md` for
capability limits and `docs/BUILD_RECEIPT.md` for exact-commit verification.
PRD/roadmap requirements and proposed test feeds are not implementation claims.
Keep observed OSS counts/dates and historical test receipts intact until remeasured.

## Change classification

- Rule/configuration semantics: update rule schema/tests and relevant docs.
- Knowledge/entity semantics: preserve evidence and temporal correction behavior.
- Donor extraction: add/update golden parity corpus, provenance ledger and rollback.
- New integration, schema, API, workflow, permission, retention, or security behavior: write an ADR before implementation.

## Forbidden repository content

Secrets, provider tokens, passwords, real message bodies/attachments, database dumps, private embeddings, access logs containing content, and generated local environments.
