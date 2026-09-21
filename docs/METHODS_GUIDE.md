# How Email Brain works

Updated 2026-09-21. A plain-language map of the engineering methods and their
product purpose. This explains the current design; it does not enable new features.
Use [implementation status](IMPLEMENTATION_STATUS.md) for availability and
[build receipts](BUILD_RECEIPT.md) for exact tested revisions.

## The short version

Email Brain does repeatable work once, saves its evidence, and lets a person or
assistant ask focused questions later. Code handles fetching, permissions,
format checks, indexing, exact rules and retries. Models may eventually propose
interpretations; they do not control access or execute mailbox actions.

There are three independent loops:

```text
Read:    provider changes -> retained evidence -> supported text -> search
Learn:   owner/assistant feedback -> typed proposal -> review -> versioned update
Develop: missing capability -> development request -> Factory review -> tested release
```

The read loop has a synthetic executable foundation. Learning currently applies
only a narrow reviewed sender-rule slice; people/project/obligation updates are
planned. Factory builds the product but is not required for it to run. Hosted
independent operation and assistant connections still need implementation/acceptance.

## Why each method exists

| Method | What it means for the owner | Current use or remaining boundary |
|---|---|---|
| Provider cursor | Remember where import stopped instead of rereading the inbox | Fastmail durable worker; Gmail/Graph/IMAP contracts need durable integration |
| Atomic checkpoint | Save the covered mail outcomes and progress together, or neither | Implemented; prevents a crash from skipping unsaved evidence |
| Reconciliation | Compare a complete provider inventory against the local view | Implemented Fastmail worker logic; incomplete listings cannot prove deletion |
| Immutable evidence | Retain original bytes and prior interpretations while retained | Implemented; a new parser/result does not rewrite an old citation |
| Per-part receipt | Record that each attachment arrived, including why it is unread | Implemented; a receipt is not proof that its contents were extracted |
| Source-bound extraction | Process precisely the approved message version and attachment bytes | Implemented synthetic PDF API/library/operator; owner UI/live policy pending |
| Idempotency | Retrying the same intent does not create a second operation | Implemented proposal/job boundaries; future provider effects still need reconciliation |
| Lease and publication fence | Give a worker temporary ownership, then recheck before saving | Implemented; expired/replaced/revoked workers cannot publish stale results |
| Full-text search (FTS) | Search stored words without sending each query's entire mailbox to AI | Implemented PostgreSQL body/text-attachment search; PDF search is opt-in |
| Hybrid retrieval | Combine exact/word matches with meaning-based candidates | Planned, benchmark-gated; vector storage is not currently installed |
| Temporal facts | Remember both what was believed and when a correction became known | Planned relational project/person/obligation state, not current tables |
| Typed control plane | Accept a small validated request instead of arbitrary code or SQL | REST proposal foundation exists; MCP and most proposal application are planned |
| Forced row-level security | Add database-level tenant checks behind the API's checks | Implemented owner-only foundation; team grants and production identity pending |

[Architecture](ARCHITECTURE.md), [data model](DATA_MODEL.md) and
[code map](CODE_MAP.md) provide the implementation details.

## Four records that must not be confused

Suppose a fictional Melron email says “the revised rent roll is attached.”

1. **Source evidence:** the retained message and exact attachment bytes. Hashes
   identify those bytes; they do not establish the sender's honesty or authenticity.
2. **Extracted evidence:** supported text plus its source/part/parser identity.
   An attachment can be preserved but deferred, partially extracted or unscanned.
3. **Interpretation:** “the rent changed” or “we owe a reply.” This is a derived
   claim that needs evidence, uncertainty and correction history. Those projectors
   are not implemented yet.
4. **Action:** creating a draft or filing the message. This needs separate
   authority, an exact preview and an executor; no provider-write path exists today.

An extracted sentence is not automatically a verified business fact, and a verified
fact is not permission to act. The [worked walkthrough](PRODUCT_WALKTHROUGH.md)
shows this distinction throughout a project.

## Recovering a message is different from reading its PDF

If MIME parsing fails, the **message-recovery channel** can retry retained mail
under an explicit parser-bound grant. Its owner screen and bounded operator command
exist. It does not grant general document processing permission.

If the body is already searchable but its PDF is deferred, the **document channel**
uses a separate attachment approval, worker identity, processor/policy and immutable
page result. Its API/library and operator command exist; its owner UI does not yet.
A PDF-only query uses `include_documents: true`; default search excludes those
document results. A completed job may record a partial/deferred/failed extraction,
so inspect the result rather than treating job completion as successful reading.

Neither channel changes provider mail. The default application image excludes
the PDF reader; the separate synthetic PDF image always reports **unscanned**.
No Office extraction, OCR, malware-safety or live-document acceptance is implied.
[MIME recovery](RECOVERY_JOBS.md) · [PDF processing](DOCUMENT_PROCESSING.md).

## How a correction becomes a durable improvement

Current sender-rule workflow:

1. Submit a typed rule proposal and review it.
2. Simulate a bounded sample of the proposed effects.
3. Explicitly activate against the expected current rules revision.
4. Search shows virtual categories from the active ruleset.
5. If necessary, roll back by adding a new revision based on an earlier one.

Generic approval alone does not apply a rule. A virtual `_GrokBot/Review Delete`
category neither deletes nor hides provider mail. “Create a Melron project” can
currently create a proposal, not an actual project. A new parser or capability
belongs in development, not executable rule text. [Rules/feedback](RULES_AND_FEEDBACK.md).

## What belongs in the cloud, locally and in GitHub

- **Hosted target:** independent API/workers, managed PostgreSQL, private source
  objects, recoverable keys and operator alerts. Azure is the planning preference
  if it shares the existing hosting billing home; no resources are provisioned.
- **Optional local work:** evaluated local inference and a future scoped read cache.
  Neither may be required for hosted sync or lexical search to work.
- **GitHub/source checkout:** code, migrations, instructions and fictional tests.
  A Dropbox source checkout is not a place for a running database, credentials,
  private mail, object storage or model caches.
- **Mail provider:** authoritative mailbox state. Hosting on Azure does not require
  Microsoft mail, SharePoint, a Microsoft model or a second mail account.

The current encrypted local-object backend is not yet a hosted Blob adapter.
Database, object and key recovery must be tested together. See
[hosting decision](HOSTING_DECISION.md) and [deployment](DEPLOYMENT.md).

## What counts as proof

Synthetic scenarios provide coherent messages, real-format fictional attachments
and known answers. Unit tests check small contracts; real SQL tests check storage
and authorization; actual restricted-container tests check execution boundaries;
restore tests check recovery. These are complementary, not interchangeable.

Node UI-contract tests are not browser/accessibility acceptance. Fake model outputs
are not classification-quality measurements. Disposable restore timing is not a
production recovery guarantee. Public datasets are optional supplements requiring
rights/privacy/safety review, not a subscription or automatic approved feed.

Use [test mailbox plan](TEST_MAILBOX_PLAN.md) to reproduce the safe feed and
[release acceptance](RELEASE_ACCEPTANCE.md) to distinguish a merged component from
a usable pilot and a production service. The [roadmap](ROADMAP.md) owns delivery
order; [open questions](OPEN_QUESTIONS.md) records choices that still need the owner.
