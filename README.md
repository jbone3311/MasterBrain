# CW-EmailBrain

An independent, code-first intelligence layer over email. Preserve messages once,
make them searchable with evidence, and let assistants propose useful changes
without handing them the keys to the mailbox.

**Status: working synthetic-data prototype, not a hosted or live-mail product.**
The repository contains executable ingestion, PostgreSQL search, review and
recovery code, plus a separately approved synthetic PDF-to-search pipeline.
Live enrollment, production identity, production document-processing policy,
supervision and acceptance testing remain launch requirements. No real mailbox,
paid cloud resource or remote model is enabled by this repository.

Documentation updated September 21, 2026. [Verification receipts](docs/BUILD_RECEIPT.md) identify exactly what
passed; documentation updates do not certify new functionality.

## Understand the product

- [Game plan](docs/GAME_PLAN.md): the finished product and how we get there.
- [Worked product walkthrough](docs/PRODUCT_WALKTHROUGH.md): follow a fictional
  project through incoming mail, attachments, search, corrections and future actions.
- [Features and methods](docs/FEATURES_AND_METHODS.md): workflows, implementation and limits.
- [Implementation status](docs/IMPLEMENTATION_STATUS.md): working capabilities versus launch gates.
- [Roadmap](docs/ROADMAP.md): dependency-ordered milestones and measurable exits.
- [Test mailbox guide](docs/TEST_MAILBOX_PLAN.md): generate/export believable conversations, real attachments and answer keys; replay through bounded synthetic ingestion.
- [Documentation directory](docs/README.md): complete product, engineering and operations pack.

## What works now

| Area | Executable prototype |
|---|---|
| Ingest | Fastmail worker library; synthetic HTTP-to-Postgres tests; atomic checkpoints, fenced leases, quarantine and inventory reconciliation |
| Preserve | Immutable raw/evidence versions; bounded inline MIME; opt-in encrypted local objects up to 16 MiB |
| Search | PostgreSQL FTS over messages and supported text/calendar attachments, with stable evidence references |
| Read PDFs | Separate synthetic approval API/library and operator command, restricted PDF worker, immutable page evidence and opt-in document FTS; owner UI still pending |
| Review | Owner-only local UI: search, proposals, virtual sender rules, held mail, processing history/approval/cancellation |
| Recover | Human-authorized retries and separate restricted MIME worker; bounded jobs, expiry, cancellation and atomic results |
| Isolate | Tenant RLS, ownership constraints, scoped expiring bootstrap credentials and negative authorization tests |
| Test | Fictional inbox seeding, actual synthetic attachment bytes, mocked provider contracts, real PostgreSQL CI and disposable SQL/object restore drills |

The known-answer mailbox creates connected conversations and corrections with
PDF, Excel, CSV, Word, calendar, image, forwarded-message and archive attachments.
The files are real formats with fictional contents; this does **not** mean the
production parser extracts every format. Follow the
[export/replay guide](docs/TEST_MAILBOX_PLAN.md) to reproduce them without a mail
account, subscription or remote model.

Gmail and Graph have offline-tested read libraries; IMAP has an injected-session
contract. They are **not yet durable live connectors**. The optional Ollama library
is candidate-only, tested with fake responses and not wired into ingestion.
Vectors, people/project/obligation projections, MCP, provider drafts, moves,
sending and deletion are not implemented.

`_GrokBot/Review Delete` is a virtual search label—not a provider folder or deletion
queue. Processing completion does not mean PDF/Office extraction succeeded;
every attachment has its own outcome.

A separate [restricted PDF worker](docs/PDF_WORKER.md) now provides source-bound,
page-level extraction groundwork with explicit partial/deferred outcomes. It is
now connected to a separate [synthetic document approval API/library](docs/DOCUMENT_PROCESSING.md),
immutable results and opt-in document search. Ordinary ingestion still defers PDFs;
The [PDF operator command](docs/DOCUMENT_CONTROLLER.md) is explicit and separate;
owner UI controls are pending. The default image has no PDF reader and no malware-safety
claim is made.

## What comes next

1. Finish the document-processing owner experience around the approved API/library
   and separate bounded operator command: safe UI, cited results and review controls.
   Preserve body/evidence identity and separately resolve scanner/live policy.
2. Complete supervised read-only operation, production identity, managed storage,
   recoverable keys and operator alerts; then accept one disposable live provider.
3. Build evaluated project/reply state and assistant access; add separately
   approved mailbox actions only after those foundations.

See [roadmap acceptance gates](docs/ROADMAP.md) and the
[Factory next assignment](docs/FACTORY_HANDOFF.md#suggested-next-issue).

## What the finished product adds

Project/person/thread memory and open commitments; evaluated local classification;
Grok/ChatGPT/Claude query and feedback tools; explicit team permissions; and
previewed mailbox filing/drafts through a separately approved executor. These are
delivery targets, not enabled features. Cloud inference and vector search are
optional enhancements, not prerequisites for keeping mail searchable.

## How the design works

```text
Provider changes -> preserve evidence -> parse/account for every part -> search
                                              |
                               rules first; optional model candidates later
                                              |
Assistant/user request -> typed proposal -> policy + human review -> versioned change
```

Future mailbox effects use a separate approved executor. Email and model output
cannot authorize tools or account access. Factory governs development; the deployed
product must not depend on Factory or Jim's computer running.

## Hosting direction

Prefer the same Azure billing home as RealEstateOS, with **separate Email Brain
resources and permissions**: API/workers, private managed PostgreSQL, private Blob
storage, managed identities and Key Vault. This is not a deployment or a requirement
to use Microsoft mail/SharePoint. Keep live databases, secrets, objects and model
caches outside Dropbox. See [hosting](docs/HOSTING_DECISION.md).

## Run and verify

The separate [approved-processing command](docs/PROCESSING_CONTROLLER.md) runs
bounded recovery jobs with explicit private configuration. It does not enroll an
account, install a service or give the API Docker access.

[Local development](docs/LOCAL_DEVELOPMENT.md) explains disposable PostgreSQL,
private credentials, synthetic seeding and loopback-only serving.

```sh
uv sync --locked --extra dev
uv run ruff check .
uv run mypy src
uv run pytest -q
node --test tests/web_session.test.cjs tests/web_processing.test.cjs
uv run python scripts/deployment_gate.py
uv run python scripts/check_docs.py
uv run email-brain --help
```

PostgreSQL tests need a disposable `email_brain_test*` database and
`EMAIL_BRAIN_TEST_ADMIN_DSN`; CI supplies it. Local skips are not passes.
See the [build receipt](docs/BUILD_RECEIPT.md) for exact tested commits and limits.

## For the implementation team

[Code map](docs/CODE_MAP.md) · [Factory handoff](docs/FACTORY_HANDOFF.md) ·
[Backlog](docs/BACKLOG.md) · [Open decisions](docs/OPEN_QUESTIONS.md) ·
[Contributing](CONTRIBUTING.md) · [Release acceptance](docs/RELEASE_ACCEPTANCE.md)

[Documentation maintenance](docs/DOCUMENTATION_STANDARD.md) defines status terms,
authoritative records and the updates required alongside each feature. A tested
component, integrated workflow and live-accepted service are different milestones.

Read [PRODUCT.md](PRODUCT.md), [AGENTS.md](AGENTS.md), security, architecture and
accepted [ADRs](docs/DECISIONS.md) before changing behavior. Security invariants and
explicit accepted ADRs govern conflicts. Update implementation, tests, migrations,
rollback notes and documentation together.

Private proprietary product; dependency licenses remain separate. Never commit
real messages/attachments, credentials, dumps or private embeddings. Committed/CI
mail fixtures are synthetic only. Public samples require the [adoption gate](docs/PUBLIC_EMAIL_TEST_DATA.md).
