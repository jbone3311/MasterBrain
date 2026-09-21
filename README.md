# CW-EmailBrain

Private, multi-user, evidence-first email intelligence infrastructure.

Email Brain incrementally synchronizes supported mail providers, preserves immutable evidence, performs deterministic classification and retrieval, and exposes bounded API/MCP interfaces to Grok, ChatGPT, Claude, and other clients. Models propose structured interpretations; policy-controlled code owns authorization and mailbox effects.

## Repository status

This repository is an **executable, synthetic-data-only prototype**, not a production
mail service. It includes:

- the full product and architecture pack in [`docs/`](docs/README.md);
- Factory-facing product and agent contracts;
- a dependency-light Python domain core;
- a safe declarative rule evaluator with tests;
- connector and event contracts;
- PostgreSQL tenant/RLS migrations, atomic ingestion, immutable evidence versions,
  full-text search, attachment receipts and bounded plain-text extraction;
- bounded calendar-invitation source extraction and realistic synthetic attachment
  format tests across all four provider read boundaries;
- expiring tenant-bound bootstrap credentials, REST API and a small owner review UI;
- idempotent typed proposals and optimistic-concurrency human review;
- human-reviewed sender rules with bounded simulation, explicit activation,
  immutable revision history, rollback and virtual search labels;
- a read-only Fastmail HTTP transport and resumable worker library with fenced leases,
  certified inventory reconciliation, expired-history recovery, incremental changes,
  bounded retries, durable MIME quarantine and owner-scoped processing status;
- resumable fictional-inbox seeding with varied mail and attachments;
- offline-tested Gmail/Graph read libraries and an injected-session IMAP contract
  (not live connectors or durable provider workers yet);
- owner import-health and held-message review with bounded metadata-only paging,
  explicit human retry, immutable attempt history and parser-versioned evidence;
- opt-in loopback Ollama classification library with fake-response tests and
  model-digest checks (no daemon contacted or model enabled by default);
- a disposable PostgreSQL logical backup/restore drill workflow;
- locked dependencies, CI with a real PostgreSQL service, and a repository gate.

It does **not** connect to your mail, send anything, change folders, delete mail,
apply non-rule proposals, or deploy paid cloud resources. Rules affect only virtual
labels inside Email Brain, never the mailbox. Hosted OIDC, full team
permissions, binary attachment extraction, provider enrollment, and production
operations remain launch gates. See [implementation status](docs/IMPLEMENTATION_STATUS.md).

## Start here

[Executive review](docs/EXECUTIVE_REVIEW.md) · [Build receipt](docs/BUILD_RECEIPT.md) ·
[Factory intake review](docs/FACTORY_INTAKE_REVIEW.md) ·
[Hosting recommendation](docs/HOSTING_DECISION.md) · [Open decisions](docs/OPEN_QUESTIONS.md)

The worker is exercised through synthetic HTTP → PostgreSQL tests, not a real
mailbox. See [worker contract and recovery limits](docs/READ_WORKER.md).

```bash
uv sync --locked --extra dev
uv run pytest -q
uv run ruff check .
uv run mypy src
uv run python scripts/deployment_gate.py
```

The PostgreSQL tests require a disposable database named `email_brain_test*` and
`EMAIL_BRAIN_TEST_ADMIN_DSN`; CI provides it. Local absence is reported as skipped,
never as database verification. Start the synthetic demo using [LOCAL_DEVELOPMENT.md](docs/LOCAL_DEVELOPMENT.md).

For available application commands:

```bash
uv run email-brain --help
```

## Binding documents

1. [`PRODUCT.md`](PRODUCT.md)
2. [`AGENTS.md`](AGENTS.md)
3. [`docs/SECURITY.md`](docs/SECURITY.md)
4. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
5. [`docs/DECISIONS.md`](docs/DECISIONS.md)
6. [`docs/FACTORY_HANDOFF.md`](docs/FACTORY_HANDOFF.md)

When these conflict, security invariants and explicit accepted ADRs win. A behavioral change requires documentation and test updates in the same pull request.

## First vertical slice

Implement one read-only provider connector through immutable evidence, normalization, PostgreSQL/RLS, lexical search, replay tests, metrics, and restore verification. Models, vectors, and mailbox writes are later increments.

## Data warning

Never commit real messages, credentials, OAuth tokens, database dumps, vectors derived from private mail, or unsanitized fixtures. Use synthetic test data only.
