# Features and methods

Updated 2026-09-21. “Implemented” means bounded local/CI synthetic behavior, not
production. [Status](IMPLEMENTATION_STATUS.md) and [receipts](BUILD_RECEIPT.md) govern claims.

See the [worked walkthrough](PRODUCT_WALKTHROUGH.md) for the owner experience,
attachment-format matrix and failure examples. Each method below supports a
specific product outcome; none grants new mailbox or remote-model authority.

| Owner benefit | Method | Current boundary |
|---|---|---|
| Incremental import | Native cursors, bounded pages, atomic checkpoint, leased worker, certified inventory | Fastmail worker; offline Gmail/Graph libraries; injected IMAP contract; no live enrollment |
| Search with sources | PostgreSQL FTS, account filters, immutable evidence IDs, bounded excerpts | Working; no vectors or project/entity filters |
| Account for attachments | Per-part receipts, source hashes, duplicate links, explicit outcomes | Plain/CSV/calendar text; binary PDF/Office/image/archive extraction deferred |
| Read selected PDFs safely | Source/part/hash verification, restricted image, bounded page text and strict parent validation | Standalone tested worker; no integrated approval, stored extraction, FTS or malware scanner |
| Recover held mail | Owner retry; parser versions; isolated jobs bound to receipt/parser/expiry | API/UI, worker library and explicit bounded operator CLI; no hosted supervision |
| Organize senders | Declarative match, review, bounded simulation, activation and immutable rollback | Narrow exact-domain persisted rules; virtual search labels only |
| Send feedback | Typed evidence-linked proposals with idempotency and review state | REST works; most approved proposal types apply nothing; MCP absent |
| Track people/projects | Relational entities/aliases, evidence-linked facts, reversible merges, valid/recorded time | Planned; project proposal is not a created project |
| Track promises/replies | Evidence-backed open/closed/reopened obligations and uncertainty | Planned; no measured Needs Reply classifier |
| Use local AI | Code first; bounded model input/output, digest and schema/grounding checks | Optional Ollama library, fake-response tested, not automatically invoked |
| Escalate hard cases | Minimum authorized evidence, disclosure policy, retention review, budget caps | Planned; no remote calls or silent fallback |
| Draft/file mail | Separate executor, preview-bound approval, command outbox, reconciliation | Planned; no SMTP/drafts/moves/send/delete |
| Share securely | API checks and tenant RLS, then explicit account/project grants | Owner foundation works; OIDC/invitations/team grants pending |
| Run independently | Supervised workers, managed storage, alerts, restores, deployment artifacts | Local/CI and restore drill; no hosted service |

## Code first, models second

Code handles exact identifiers, MIME structure, hashes, known rules, permissions
and retries. It is repeatable and testable, but still needs parser/version provenance
and regression tests. Models can propose ambiguous requests, aliases and summaries.
Their claimed confidence is not accuracy: evaluate against labeled cases, allow
abstention and route consequential ambiguity to review. No model receives provider
tokens or action tools. [Model strategy](AI_MODEL_STRATEGY.md).

## Follow one message through the system

1. **Read changes:** the provider adapter fetches bounded source bytes and metadata.
   A stored cursor and account lease support restart. Only Fastmail currently has
   the durable database worker; the other provider contracts are offline-tested.
2. **Keep evidence:** preserve source bytes/hash and account ownership before
   advancing progress. Default inline MIME is bounded to 1 MiB; explicitly configured
   encrypted local storage can preserve up to 16 MiB. Larger preservation is not
   permission for a larger in-process parser.
3. **Account for content:** normalization produces a versioned body; attachment
   receipts record extracted, deferred, failed or skipped outcomes. Supported
   plain/CSV/calendar text can enter FTS. PDF/Office/image/archive bytes stay deferred.
4. **Find it:** current authorized message/attachment text becomes searchable with
   evidence IDs. Old evidence remains distinguishable; a provider tombstone hides
   the current result without silently purging retained history.
5. **Improve interpretation:** today's reviewed sender rules add virtual labels.
   Future evaluated models and projectors will propose facts, obligations and
   corrections. They cannot change mailbox state merely by returning JSON.
6. **Act only through a separate boundary:** future drafts/moves require an exact
   preview, authorization and executor. There is no current provider-write path.

Each stage has a different success condition. “Imported,” “body searchable,”
“attachment extracted,” “scanned,” “fact verified” and “action executed” must not be
collapsed into one green checkmark.

## Attachment processing is a separate product workflow

**Current:** held-message recovery is tied to a quarantine receipt and an approved
MIME parser. A recovered message can still contain deferred documents. A ready
message containing a PDF is not automatically eligible for that recovery queue.

[ADR-034's separate worker](PDF_WORKER.md) now verifies exact MIME/part bytes and
extracts bounded PDF page text in an optional restricted image. That is groundwork:
no durable tenant approval, document result storage or FTS publication is connected.
Its always-unscanned result is never a replacement for scanner policy.

**Required next:** an approved attachment job must identify the immutable source
version, exact MIME part and bytes, as well as the processor/image and policy.
The worker needs resource limits and no network or provider credentials; the parent
must validate returned text and provenance before publishing a new extraction.
Cancellation, revoked access, changed sources and expired leases must prevent stale
publication. Existing body search and historical citations must survive failure.

Scanned images need OCR; encrypted documents need an explicit password policy;
damaged/unsupported/over-budget inputs need visible outcomes. Text extraction does
not establish malware safety or document truth. These are design requirements,
not newly implemented capabilities. [Next work package](BACKLOG.md#eb-006-next-source-bound-document-processing).

## How we prove usefulness

The implemented test mailbox starts from known fictional project facts, then
creates coherent conversations, revised spreadsheets, PDFs, calendar changes and
failure cases. A versioned manifest records bytes, arrivals and expected outcomes.
Replaying the same packet tests duplicate delivery, restarts and searches. Separate
readers check that our generated PDFs/Office files are valid; they are development
dependencies, not enabled production extractors.

This answers “did we store and find the right supported evidence?” It does not yet
answer “does a model understand varied real-world mail?” That requires held-out
quality evaluations, while provider reliability requires authorized live tests and
sustained operation. See [mailbox guide](TEST_MAILBOX_PLAN.md) and
[evaluation plan](TESTING_AND_EVALS.md).

## Three kinds of change

1. **Knowledge:** a proposed project/person/fact relationship with evidence. Future
   projectors apply approved changes and retain supersession history.
2. **Rules/configuration:** reviewed sender classification changes without a code
   deployment. The current virtual-rule slice already supports this narrow loop.
3. **Software:** a new parser, connector, permission or schema is development work
   for Factory, not a mutation an assistant can perform through the mail API.

Generic approval and execution are separate: approval applies nothing; rule
activation is an additional explicit step. Processing approval is a different,
expiring grant for one source/parser. [Feedback policy](RULES_AND_FEEDBACK.md).

## Review categories are not mailbox actions

`_GrokBot/Review`, `_GrokBot/Review Delete` and `_GrokBot/Needs Reply` are intended
review categories. Current rules produce virtual labels inside Email Brain; they
do not create provider folders, mark mail read or remove it from the Inbox.
Future folder/Gmail-label mapping needs an approved executor. Rule rollback does
not undo a provider move, and sending cannot be reliably compensated.

## Evidence is not the same as interpretation

The provider owns current mailbox state. Email Brain owns retained evidence and
its index. Provider deletion hides current projections without silently purging
evidence; eventual erasure follows approved retention policy. Normalization never
overwrites raw bytes. Hashes identify bytes, not a sender's authenticity or truth.

A completed processing job can contain deferred PDFs. Inspect per-part outcomes.
Calendar extraction is quoted text, not an RSVP, scheduled event or computed
recurrence. [Attachment contract](CALENDAR_ATTACHMENTS.md).

## Reliability methods in plain language

- **Atomic checkpoint:** commit stored outcomes and progress together.
- **Idempotency:** the same request key identifies the same intent across retries.
- **Lease fencing:** expired/replaced workers cannot publish stale results.
- **Certified inventory:** only complete consistent listings can establish absence.
- **Versioned evidence:** parser changes preserve old citations rather than overwriting them.
- **Reconciliation:** inspect uncertain external outcomes before retrying; no universal exactly-once promise.

[Architecture](ARCHITECTURE.md) · [Code map](CODE_MAP.md) · [Data model](DATA_MODEL.md) ·
[API/MCP](API_MCP_SPEC.md) · [Security](SECURITY.md) · [Operations](OPERATIONS_RUNBOOK.md)
