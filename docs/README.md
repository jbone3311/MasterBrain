# Email Brain / Email OS

Status: target architecture plus an executable bounded prototype  
Documentation updated: 2026-09-21; exact tested revisions are in the build receipt.
Source health measurements and historical validation retain their own dates.

Email Brain's target is a private, multi-user intelligence layer that synchronizes
mail, maintains people/project/thread/obligation state and gives assistants bounded
evidence instead of whole mailboxes. The current prototype implements only a
bounded portion: synthetic ingestion/search, review, virtual rules and recovery.
It also connects approved synthetic PDFs to restricted extraction, immutable page
evidence and opt-in search through a separate API/library and explicit operator
command. The [owner PDF screen](DOCUMENT_REVIEW_SCREEN.md) now provides separate
selection/approval/history/cancellation and cited pages; live acceptance is pending.

## Reading paths

- **Owner:** [game plan](GAME_PLAN.md), [features/methods](FEATURES_AND_METHODS.md),
  [how it works](METHODS_GUIDE.md),
  [worked product walkthrough](PRODUCT_WALKTHROUGH.md),
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

## Find the answer quickly

| Question | Authoritative starting point |
|---|---|
| What will this product ultimately do? | [Game plan](GAME_PLAN.md), then [PRD](PRD.md) |
| What actually works, and how? | [Features/methods](FEATURES_AND_METHODS.md), [status](IMPLEMENTATION_STATUS.md), [code map](CODE_MAP.md) |
| What do the technical methods mean for me? | [Methods guide](METHODS_GUIDE.md): evidence, retries, search, corrections and permission boundaries |
| Where will it run and what stays local? | [Hosting decision](HOSTING_DECISION.md), [deployment](DEPLOYMENT.md) |
| What is the team building next? | [Identity foundation](BACKLOG.md#eb-007-next-production-identity-foundation), [roadmap sequence](ROADMAP.md#next-build-packages), [Factory assignment](FACTORY_HANDOFF.md#suggested-next-issue) |
| How do we test believable mail and attachments? | [Runnable mailbox guide](TEST_MAILBOX_PLAN.md), [evaluation plan](TESTING_AND_EVALS.md) |
| What has actually passed? | [Exact-commit build receipt](BUILD_RECEIPT.md), not roadmap targets |
| How should a developer contribute? | [Contributor guide](../CONTRIBUTING.md), [Factory handoff](FACTORY_HANDOFF.md) |
| What must pass before a release? | [Release acceptance/evidence](RELEASE_ACCEPTANCE.md), [security](SECURITY.md) |
| Which decisions still need Jim? | [Open questions](OPEN_QUESTIONS.md); safe synthetic work can continue |

The documentation review explains the owner scenario, methods, attachment coverage,
failure behavior and dependency-ordered delivery plan. The latest consistency pass
aligns current claims through ADR-040, explains the methods in plain language,
and checks contribution/release guides and GitHub review templates automatically.
It separates completed synthetic PDF/read-operator and API token/mapping work from
browser identity lifecycle, hosted operation and live acceptance. The
[configured identity foundation](IDENTITY_AUTH.md) is executable, but does not
implement browser login/MFA or certify a real issuer. Bootstrap remains a separate mode.
[Documentation ownership/status terms](DOCUMENTATION_STANDARD.md)
keep future changes traceable. Browser/accessibility and live/scanner policy remain
pending for the document channel. Research counts retain their actual observation dates; no hosted
deployment or Factory audit is claimed.

## Executive architecture review

Start with [EXECUTIVE_REVIEW.md](EXECUTIVE_REVIEW.md),
[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md),
[FACTORY_INTAKE_REVIEW.md](FACTORY_INTAKE_REVIEW.md), and
[HOSTING_DECISION.md](HOSTING_DECISION.md). Production controls below are requirements,
not a claim that all integrations are implemented or deployed.

The design is sound after five refinements:

1. **Hosted Postgres is authoritative.** For multi-user remote access, use a managed PostgreSQL service with point-in-time recovery, private networking, encryption, and tested exports. Preserve the option for `pgvector` after measured retrieval need; vectors are not part of the current implementation. An encrypted SQLite database may be a local read cache, but is not the shared source of truth.
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
                         disclosure/budget permission?
                         yes: remote; no: defer/review
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

A modular Python service with HTTP endpoints, separate privileged workers, managed
PostgreSQL and encrypted private object storage. PostgreSQL 17 is the current CI
baseline, not a claim that it is the newest release. Start with one explicitly
enrolled read-only provider, FTS, evidence and virtual review categories. Fastmail
is the engineering default; the owner's first account is still undecided. Add
`pgvector` only after measured lexical misses justify semantic retrieval; it is not
a first-release prerequisite. Add a transactional action outbox with the separately
approved mailbox executor, not an implied write path in the read-only pilot.

Use provider-native change tracking: Gmail partial sync through `history.list` ([Google sync guide](https://developers.google.com/workspace/gmail/api/guides/sync)); Microsoft Graph per-folder delta links ([message delta](https://learn.microsoft.com/en-us/graph/api/message-delta?view=graph-rest-1.0)); JMAP changes/queryChanges for Fastmail ([RFC 8621](https://www.rfc-editor.org/rfc/rfc8621)); and UID/UIDVALIDITY plus periodic reconciliation for iCloud IMAP ([Apple settings](https://support.apple.com/en-ie/102525)). Notifications are hints; stored cursors are truth.

## Documents

| Document | Purpose |
|---|---|
| [GAME_PLAN.md](GAME_PLAN.md) | Finished experience, delivery sequence and release bar |
| [FEATURES_AND_METHODS.md](FEATURES_AND_METHODS.md) | Feature-by-feature methods and current limitations |
| [METHODS_GUIDE.md](METHODS_GUIDE.md) | Plain-language methods, evidence versus interpretation, distinct processing channels and proof |
| [PRODUCT_WALKTHROUGH.md](PRODUCT_WALKTHROUGH.md) | Worked owner scenario, format coverage, failure behavior and deployment split |
| [DOCUMENTATION_STANDARD.md](DOCUMENTATION_STANDARD.md) | Status vocabulary, authoritative records and maintenance checklist |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | Developer entry path, checks, review and Factory boundaries |
| [RELEASE_ACCEPTANCE.md](RELEASE_ACCEPTANCE.md) | Merge/pilot/release distinctions, gate register, metrics and evidence record |
| [CODE_MAP.md](CODE_MAP.md) | Actual files and operation paths |
| [IDENTITY_AUTH.md](IDENTITY_AUTH.md) | Configured RFC/Entra access tokens, database mappings, revocation, audit, upgrade and remaining login gates |
| [READ_CONTROLLER.md](READ_CONTROLLER.md) | Bounded Fastmail read command, private preflight, authority checks and remaining live/supervision gates |
| [PDF_WORKER.md](PDF_WORKER.md) | Source-bound restricted PDF reader, isolation and format limits |
| [DOCUMENT_PROCESSING.md](DOCUMENT_PROCESSING.md) | Separate synthetic approval API/library, durable results, opt-in search and remaining operator/live gates |
| [DOCUMENT_CONTROLLER.md](DOCUMENT_CONTROLLER.md) | Explicit PDF command, private configuration, preflight, worker identity and operational limits |
| [DOCUMENT_REVIEW_SCREEN.md](DOCUMENT_REVIEW_SCREEN.md) | Owner PDF selection/approval/history/cancel, opt-in search, cited pages and uncertainty handling |
| [TEST_MAILBOX_PLAN.md](TEST_MAILBOX_PLAN.md) | Executable fictional generator/export/replay, attachment formats, answer keys and remaining soak gaps |
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

## Keeping this pack current

Follow [DOCUMENTATION_STANDARD.md](DOCUMENTATION_STANDARD.md) for ownership,
status language, evidence and the per-feature update checklist.

New operator workflow: [approved-processing command](PROCESSING_CONTROLLER.md),
with private configuration, preflight, bounded polling, results and rollback.

- Change a feature's contract, implementation, tests, status, roadmap and rollback
  notes in the same work package. Add an ADR before new permissions/schema/workflows.
- Run `scripts/check_docs.py`: it requires the original 16 pack documents,
  product/contributor/release/operator guides and GitHub issue/PR templates. It
  checks local paths and supported heading fragments across root/docs/GitHub Markdown.
  It does not verify remote URLs, factual correctness, all Markdown syntax or
  browser accessibility. See the [checker's scope](DOCUMENTATION_STANDARD.md#automated-check-scope).
- Keep test counts in exact-commit receipts. Preserve historical results and source
  snapshot dates; a documentation edit is not a fresh benchmark or OSS activity scan.
- Proposed fixtures/services must remain labeled proposed until code, provenance
  and acceptance evidence exist. Never count unsupported extraction as success.
- Preserve concurrent GitHub contributions; integrate and recheck rather than
  overwriting main. Factory remains an independent reviewer.

## License and data note

The private Product remains proprietary; no public OSS license is granted. Review
dependency licenses before distribution. Mail, credentials, real-mail fixtures,
databases, private vectors and backups never belong in Git. Synthetic fixtures only.
