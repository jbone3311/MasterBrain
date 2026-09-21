# Email Brain / Email OS

Status: target architecture plus an executable bounded prototype  
Documentation reviewed: 2026-09-20; source health measurements retain their own dates.

Email Brain's target is a private, multi-user intelligence layer that synchronizes
mail, maintains people/project/thread/obligation state and gives assistants bounded
evidence instead of whole mailboxes. The current prototype implements only a
bounded portion: synthetic ingestion/search, review, virtual rules and recovery.

## Reading paths

- **Owner:** [game plan](GAME_PLAN.md), [features/methods](FEATURES_AND_METHODS.md),
  [status](IMPLEMENTATION_STATUS.md), [hosting](HOSTING_DECISION.md), [open choices](OPEN_QUESTIONS.md).
- **Builder/Factory:** [code map](CODE_MAP.md), [handoff](FACTORY_HANDOFF.md),
  [architecture](ARCHITECTURE.md), [ADRs](DECISIONS.md), [roadmap](ROADMAP.md), [backlog](BACKLOG.md).
- **Tester:** [test mailbox plan](TEST_MAILBOX_PLAN.md), [local run](LOCAL_DEVELOPMENT.md),
  [coverage](TEST_COVERAGE_MATRIX.md), [evaluation](TESTING_AND_EVALS.md), [receipts](BUILD_RECEIPT.md).
- **Operator/security reviewer:** [security](SECURITY.md), [deployment](DEPLOYMENT.md),
  [runbook](OPERATIONS_RUNBOOK.md), [restore](RESTORE_DRILL.md), [processing controls](PROCESSING_REVIEW_SCREEN.md).

## How to read status claims

The PRD and target sections describe requirements, not shipped integrations.
Implementation status describes local/CI behavior. Build receipts tie validation
to exact commits and retain historical results without rewriting them as current.
Accepted ADRs may supersede earlier boundaries; the latest applicable decision
wins, subject to security invariants. A planning choice is not cloud provisioning,
an SDK contract is not live acceptance, and an approved proposal is not execution.

## Executive architecture review

Start with [EXECUTIVE_REVIEW.md](EXECUTIVE_REVIEW.md),
[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md),
[FACTORY_INTAKE_REVIEW.md](FACTORY_INTAKE_REVIEW.md), and
[HOSTING_DECISION.md](HOSTING_DECISION.md). Production controls below are requirements,
not a claim that all integrations are implemented or deployed.

The design is sound after five refinements:

1. **Hosted Postgres is authoritative.** For multi-user remote access, use a managed PostgreSQL service with point-in-time recovery, `pgvector`, private networking, encryption, and tested exports. An encrypted SQLite database may be a local read cache or single-user edge replica, but is not the shared source of truth.
2. **A control plane mediates learning.** Assistants submit typed proposals. Safe knowledge updates may auto-apply; attention-changing rules require review; code/schema/security changes become Factory work. No model edits production rules or source code directly.
3. **Mailbox effects are commands, not side effects of inference.** Classification produces a proposed action. A policy engine validates it; an idempotent executor performs it. Draft, move/label, archive, and delete privileges are separately scoped. Sending and permanent deletion are approval-gated.
4. **Tenant isolation is defense in depth.** Every owned record has `tenant_id`; authorization is checked in the API and enforced again with PostgreSQL row-level security (RLS). Workers use tenant-scoped identities. PostgreSQL notes that table owners and `BYPASSRLS` roles can bypass policies, so the runtime role must be neither ([PostgreSQL RLS](https://www.postgresql.org/docs/17/ddl-rowsecurity.html)).
5. **Email is hostile data.** Message text, attachments, retrieved pages, and model output cannot issue instructions or invoke tools. A quarantined reader produces schema-validated facts; a separate policy-controlled actor performs permitted operations. This follows the defense-in-depth and dual-LLM patterns in the [OWASP prompt-injection guidance](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html).

## Target shape

```text
Gmail / Graph / Fastmail / iCloud
              |
      provider connectors
              v
 event inbox -> raw evidence -> normalize -> deterministic rules
                                      |             |
                                      |       confident result
                                      v             |
                                local model --------+
                                      |
                               uncertain/high risk
                                      v
                               remote model
                                      |
                         schema validation + policy
                                      v
         Postgres: messages, FTS, vectors, entities, state, audit
                    |                              |
              Query API/MCP                 Control plane
                    |                    proposals/review/rollback
          Grok / ChatGPT / Claude                  |
                    |                         action outbox
                    +------------------------------+
                                      |
                              mailbox executor
```

## Non-negotiable invariants

- Raw evidence is immutable and encrypted; derived state is versioned and rebuildable.
- Cursor/checkpoint advancement never precedes durable processing of the covered changes.
- Every derived fact, answer, rule, and action can be traced to evidence and versions.
- All writes are idempotent. Model retries cannot duplicate mailbox actions.
- Search and assistant tools are tenant-scoped and return bounded results.
- Models never receive provider credentials, database superuser credentials, or unrestricted network tools.
- Nothing auto-sends or permanently deletes in the initial release.
- A global action kill switch and per-account read-only mode always exist.

## Recommended v1

A modular Python service with FastAPI-compatible HTTP endpoints, background workers, managed PostgreSQL 17+ with `pgvector`, object storage for encrypted raw MIME/attachments, and a transactional outbox. Start with one Gmail or Fastmail account, read-only sync, normalization, PostgreSQL full-text search, evidence display, and review folders. Add model extraction only after replay and deletion handling are reliable. Add semantic retrieval only after lexical retrieval misses are measured.

Use provider-native change tracking: Gmail partial sync through `history.list` ([Google sync guide](https://developers.google.com/workspace/gmail/api/guides/sync)); Microsoft Graph per-folder delta links ([message delta](https://learn.microsoft.com/en-us/graph/api/message-delta?view=graph-rest-1.0)); JMAP changes/queryChanges for Fastmail ([RFC 8621](https://www.rfc-editor.org/rfc/rfc8621)); and UID/UIDVALIDITY plus periodic reconciliation for iCloud IMAP ([Apple settings](https://support.apple.com/en-ie/102525)). Notifications are hints; stored cursors are truth.

## Documents

| Document | Purpose |
|---|---|
| [GAME_PLAN.md](GAME_PLAN.md) | Finished experience, delivery sequence and release bar |
| [FEATURES_AND_METHODS.md](FEATURES_AND_METHODS.md) | Feature-by-feature methods and current limitations |
| [CODE_MAP.md](CODE_MAP.md) | Actual files and operation paths |
| [TEST_MAILBOX_PLAN.md](TEST_MAILBOX_PLAN.md) | Proposed realistic fictional feed, attachment formats and answer keys |
| [PUBLIC_EMAIL_TEST_DATA.md](PUBLIC_EMAIL_TEST_DATA.md) | External corpus shortlist and adoption gates |
| [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) | Authoritative current capability boundaries |
| [BUILD_RECEIPT.md](BUILD_RECEIPT.md) | Exact-commit verification, historical results and explicit limits |
| [PROCESSING_REVIEW_SCREEN.md](PROCESSING_REVIEW_SCREEN.md) | Current owner processing workflow and safety semantics |
| [PRD.md](PRD.md) | Users, scope, requirements, metrics |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Components, flows, boundaries, invariants |
| [SECURITY.md](SECURITY.md) | Threat model and controls |
| [DATA_MODEL.md](DATA_MODEL.md) | Authoritative entities and lifecycle |
| [API_MCP_SPEC.md](API_MCP_SPEC.md) | REST and MCP contracts |
| [RULES_AND_FEEDBACK.md](RULES_AND_FEEDBACK.md) | Learning/control-plane policy |
| [EMAIL_PROVIDER_CONNECTORS.md](EMAIL_PROVIDER_CONNECTORS.md) | Gmail, Graph, Fastmail, iCloud |
| [AI_MODEL_STRATEGY.md](AI_MODEL_STRATEGY.md) | Code/local/remote escalation |
| [OSS_EVALUATION.md](OSS_EVALUATION.md) | Reuse-versus-reference review |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Secure hosted topology |
| [ROADMAP.md](ROADMAP.md) | Phases and exit criteria |
| [TESTING_AND_EVALS.md](TESTING_AND_EVALS.md) | Correctness, retrieval, model, security tests |
| [OPERATIONS_RUNBOOK.md](OPERATIONS_RUNBOOK.md) | Routine operations and incidents |
| [DECISIONS.md](DECISIONS.md) | Accepted ADRs and deferred choices |
| [FACTORY_HANDOFF.md](FACTORY_HANDOFF.md) | Build order and acceptance gates |
| [BACKLOG.md](BACKLOG.md) | Concrete build tickets |
| [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) | Owner decisions parked without blocking synthetic work |
| [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md) | Run/test the prototype |
| [OSS_HEALTH.md](OSS_HEALTH.md) | Stars/watchers/commits and maintenance evidence |
| [COMMUNITY_RESEARCH.md](COMMUNITY_RESEARCH.md) | User reports and evaluation implications |
| [COMPETITIVE_LANDSCAPE.md](COMPETITIVE_LANDSCAPE.md) | Commercial/OSS landscape, differentiation, and product implications |

## Explicit non-goals for v1

- A general email client UI.
- Automatic sending or permanent deletion.
- Treating generated summaries as source evidence.
- Training a foundation model on private email.
- A graph database before relational temporal facts prove insufficient.
- Exposing PostgreSQL, provider tokens, or an unauthenticated MCP server to the public internet.

## License and data note

The private Product remains proprietary; no public OSS license is granted. Review
dependency licenses before distribution. Mail, credentials, real-mail fixtures,
databases, private vectors and backups never belong in Git. Synthetic fixtures only.
