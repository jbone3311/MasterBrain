# Product Requirements Document

Updated 2026-09-21. This is the ultimate product contract, not an implemented
feature list. [Features/methods](FEATURES_AND_METHODS.md) maps each requirement to
current behavior; [status](IMPLEMENTATION_STATUS.md) identifies remaining gates.

## Release boundaries

- **Current prototype:** synthetic read/search/evidence/review, narrow virtual
  sender rules, bounded attachment handling and durable recovery API/UI/libraries.
- **First live release:** one explicitly enrolled read-only provider, hosted
  identity/storage/supervision, safe processing policy, recovery and operator acceptance.
- **Later capabilities:** evaluated state/inference, team grants/MCP and separately
  approved mailbox effects. No automatic send or permanent delete in the initial release.

Use [GAME_PLAN.md](GAME_PLAN.md) for owner intent and [ROADMAP.md](ROADMAP.md)
for the current dependency order. Numeric quality/SLO goals below are targets.

The [product walkthrough](PRODUCT_WALKTHROUGH.md) translates these requirements
into an owner scenario with explicit implementation boundaries. The PRD is the
destination; it does not override missing features recorded in implementation status.

## Product statement

Email Brain turns multiple mailboxes into a secure, searchable, current operating memory while keeping repetitive work in deterministic code. It is a service beneath assistants, not another assistant that rereads mail.

## Users and tenancy

- **Owner:** connects accounts, sets policies, approves destructive behavior, exports/deletes data.
- **Member:** searches mail and manages their own or shared workspace data as granted.
- **Reviewer:** approves proposed rules, entity merges, and mailbox actions.
- **Operator:** handles deployment and incidents without default access to message bodies.
- **Assistant client:** Grok/ChatGPT/Claude using narrowly scoped API/MCP credentials on behalf of a user.

A tenant may be one person or a household/team. Accounts and records belong to exactly one tenant; resources may be shared through explicit grants, never inferred from email participants.

## Jobs to be done

- “Show everything active with Tim, including projects, promises, and the last evidence.”
- “Find the term-sheet discussion even if I do not remember the wording.”
- “Put obvious promotions in `_GrokBot/Review Delete`, but do not delete them.”
- “Draft a reply using the thread state, but let me approve it in my mail client.”
- “I invested in Melron—associate its people/domains with that project and propose a rule.”
- “Turn a recurring accepted classification into a deterministic rule.”
- “Tell Factory when I have requested a genuinely new capability.”

## Functional requirements

### Ingestion and evidence

- Connect Fastmail JMAP, Gmail API, Microsoft Graph, and iCloud/generic IMAP.
- Perform incremental, resumable, idempotent synchronization with full-resync recovery.
- Retain immutable raw MIME or equivalent provider evidence plus hashes and provider metadata.
- Normalize MIME, character sets, HTML, quotations, signatures, trackers, attachments, identities, and threads without discarding raw evidence.
- Process supported attachments independently of whether the containing message
  body is already searchable. Bind approval/results to source evidence and part
  hashes; expose unsupported/encrypted/failed/over-budget outcomes. Scanning,
  text extraction and OCR are separate capabilities, not a single success flag.

### Organization and state

- Apply deterministic rule matching before model inference.
- Maintain categories, tags, mailbox mappings, people, organizations, projects, threads, obligations, requests, decisions, deadlines, and temporal facts.
- Support `_GrokBot/Review`, `_GrokBot/Review Delete`, `_GrokBot/Needs Reply`, `_GrokBot/Drafts`, and configurable domain folders/labels.
- Track proposed, approved, executed, failed, reversed, and externally changed mailbox actions.

### Search and answers

- Filter by tenant, account, mailbox, person, project, date, category, action state, and attachment metadata.
- Combine PostgreSQL full-text ranking, exact/entity lookup, vector similarity, recency, and diversity; expose component scores. Native PostgreSQL FTS is not BM25; any BM25 extension requires a separate measured decision.
- Return citations using stable message/thread/evidence identifiers.
- Bound every assistant result by count, bytes, token estimate, and authorization.

### AI and control plane

- Route tasks through deterministic code → local model → remote model based on ambiguity, impact, privacy, and measured confidence.
- Remote escalation also requires explicit disclosure permission and budget; an
  unavailable or uncertain local model must be allowed to defer without remote use.
- Require JSON Schema output and server-side validation for every inference.
- Accept assistant proposals for rules, entity/fact updates, relationships, priorities, category/folder mappings, corrections, and feature requests.
- Auto-apply only low-impact reversible changes under explicit policy; review attention-changing behavior; route structural changes to Factory.

### Actions

- Create provider drafts, labels/folders, moves, flags, and archives through an action outbox.
- Default to draft-only for replies and staging-only for deletion.
- Require explicit, fresh approval for send, permanent delete, bulk move, credential changes, and rule changes affecting protected classes.
- Provide dry run, preview, idempotency key, compensating action where possible, and immutable audit history.

## Quality attributes

- **Privacy:** raw mail stays within approved regions/systems; remote-model disclosure is policy-controlled and logged.
- **Availability:** remote search target 99.9% after v1; degraded read-only/local search when external models are unavailable.
- **Correctness:** no skipped cursor changes; no duplicate effects under retry; evidence provenance on 100% of derived state.
- **Latency:** p95 metadata/FTS query under 500 ms for a typical tenant; p95 hybrid retrieval under 1.5 s excluding model generation.
- **Recovery:** target RPO ≤15 minutes and RTO ≤4 hours for hosted production; quarterly restore proof.
- **Portability:** provider, model, embedding, storage, and MCP adapters have contracts and conformance tests.

## Success metrics

Initial targets must be validated against a labeled private corpus:

- ≥70% of messages resolved without a remote model.
- ≥95% precision for `Needs Reply`; report recall separately.
- ≥99.5% precision for `Review Delete`; zero permanent auto-delete in v1.
- ≥90% top-5 retrieval success on owner-authored test questions.
- 100% valid evidence links in sampled answers.
- <0.1% unreconciled provider-state drift after daily reconciliation.
- 0 cross-tenant reads in automated authorization tests.
- 100% of mailbox writes tied to actor, intent, approval state, policy decision, and result.
- Model cost, tokens, latency, correction rate, and escalation rate tracked per task/version.

## Out of scope until later

Autonomous send/delete, calendar/task writes, organization-wide eDiscovery, legal retention policy automation, attachment OCR for every format, and specialized graph infrastructure.

## Launch gates

A repeatable [fictional mailbox](TEST_MAILBOX_PLAN.md) must cover coherent threads,
real attachment bytes, revisions, failures and known answers. Count a deferred PDF
as deferred—not successful extraction. Generated scenarios supplement, not replace,
authorized disposable-provider, model-quality, security, accessibility and soak testing.

See [ROADMAP.md](ROADMAP.md) and [TESTING_AND_EVALS.md](TESTING_AND_EVALS.md). No phase advances on demo quality alone; replay, tenant isolation, rollback, and recovery evidence are required.
