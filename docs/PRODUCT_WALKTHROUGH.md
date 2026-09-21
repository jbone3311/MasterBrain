# Email Brain, from incoming mail to useful action

Updated 2026-09-21. This is a worked product explanation, not a claim that every
step is available. **Implemented** means synthetic local/CI behavior; **groundwork**
means a tested component without the complete workflow; **planned** means no
finished executable path. Production/live acceptance is a separate gate throughout.

## The product in one minute

Email Brain is the private service underneath your email assistants. It preserves
authorized mail, indexes supported content, and will maintain a current view of
people, projects and unfinished commitments. Grok, ChatGPT or Claude will ask the
service for a small, cited evidence bundle rather than repeatedly reading an inbox.
They will also submit proposed corrections, rules and feature requests.

Your mail provider remains the mail provider. Factory builds and audits the
software; it is not required to keep the deployed service running. The intended
hosted service remains available when your development computer is off. That
independent hosted operation is a delivery target, not today's deployment state.

## A fictional Melron project, end to end

| Step and owner experience | Method and safety boundary | Status |
|---|---|---|
| A broker sends a project introduction, PDF and rent-roll spreadsheet | Preserve source bytes and hashes; give every attachment a receipt; commit provider progress with durable outcomes | Implemented synthetic ingestion; no live enrollment |
| Search finds the introduction immediately | PostgreSQL full-text search over current authorized body and supported attachment text; retain evidence-version citations | Implemented; PDF/Excel text is not yet indexed |
| See that a PDF arrived but has not been understood | Attachment outcome distinguishes preservation from extraction; do not call a deferred document successfully read | Implemented receipts |
| Approve processing of this particular PDF | Bind permission to tenant/account, immutable source/part/hash and processor; restricted worker; validate and publish a new extraction atomically | PDF worker groundwork only; job/result/search integration next |
| A correction replaces an earlier rent figure | Keep both source versions; future project facts explicitly supersede earlier claims and cite the correction | Evidence history implemented; financial facts/projectors planned |
| Ask “what are we waiting on for Melron?” | Combine authorized thread evidence with evidence-backed open obligations; show uncertainty and unavailable documents | Planned state and assistant workflow |
| Say “make Melron a project and treat these senders as important” | Separate a project proposal from a rule proposal; validate scope and show reviewable effects | Generic proposals implemented; project application planned; narrow sender rules implemented |
| Approve a sender rule | Simulate a bounded sample, explicitly activate, append a revision; rollback appends another revision | Implemented virtual organization only |
| Ask for a reply draft or mailbox filing | Preview exact intent; separate approval and executor; reconcile uncertain provider results | Planned; no current draft, move, send or delete capability |

This distinction is essential: storing an approved project proposal is not the
same as creating a project. Likewise, a virtual `_GrokBot/Review Delete` label is
neither a provider folder nor permission to delete anything.

## What happens to attachments today?

These are implementation boundaries, not a blanket promise for all files with a
matching extension. Size, encoding, MIME structure and validation can change the
outcome. [Attachment contracts](CALENDAR_ATTACHMENTS.md) and
[PDF limits](PDF_WORKER.md) govern the exact cases.

| Input | Ordinary ingestion/search | Separate processing or next work |
|---|---|---|
| Supported plain text / CSV | Bounded text can be extracted and searched | No spreadsheet calculation or inferred business facts |
| Supported calendar parts | Bounded source text can be searched | No RSVP, calendar write or recurrence execution |
| Text-bearing PDF | Receipt retained; extraction deferred | Standalone restricted worker can return page text; not yet searchable through the application |
| Image-only PDF / image attachment | No OCR text indexed | OCR is planned; image-only is not proof of successful extraction |
| Encrypted PDF | Deferred | Standalone worker refuses password/decryption processing, including empty-password encryption |
| Excel / Word | Receipt and explicit outcome; no application text extraction | Generated files are independently validated in tests; that does not enable production readers |
| Archives / nested messages | Bounded MIME accounting; unsupported contents are not silently expanded | No arbitrary recursive extraction or attachment execution |
| Malformed or over-budget input | Failed/deferred/held outcome as specified by the relevant parser | Inspect the reason; do not repeatedly retry a permanent limitation |

The default API/MIME image excludes the PDF reader. The separate PDF image is
opt-in and reports **unscanned**; extraction success never establishes malware
safety. Held-message MIME recovery and ready-message document processing are
different permissions/workflows. A good email body must stay searchable if its
document cannot be processed.

## How the system avoids rereading everything with AI

1. Preserve and normalize each source with hashes and parser provenance.
2. Use exact code for permissions, IDs, change cursors, known sender rules,
   supported text extraction, retries and search.
3. In the planned inference workflow, send only the unresolved task and necessary
   authorized evidence to a constrained model. Validate its proposed output.
4. Reuse versioned derived results only when source, task and model/policy versions
   match. Durable inference caching is still planned, not an existing optimization.
5. Escalate only under explicit disclosure policy and budget. If no permitted
   model is available, defer or ask for review; do not silently call a cloud model.

The current local-model adapter has fake-response contract tests, not measured
mailbox classification quality. Models never decide who can read an account or
receive mailbox credentials. [Model strategy](AI_MODEL_STRATEGY.md).

## What “learning” means

- **Knowledge:** “Melron is a project I care about.” Preserve evidence, proposed
  relationships and corrections. Applying these to entity/state tables is planned.
- **Rules:** “Mail from this exact sender domain belongs in this review category.”
  The narrow reviewed virtual-rule workflow already works without a code deployment.
- **Software:** “Read a new document format” or “add another provider.” Record a
  development request for Factory; do not execute code supplied through email.

The human's authenticated request supplies authority. Text inside a message,
attachment, quoted thread or model response does not. See
[rules and feedback](RULES_AND_FEEDBACK.md) for policy and
[API/MCP specification](API_MCP_SPEC.md) for current versus future interfaces.

## Where it runs

| Location | Intended responsibility | Current reality |
|---|---|---|
| Private GitHub / development checkout | Code, docs, migrations and fictional tests | Existing private repository; canonical local placement remains an owner decision |
| One approved cloud billing home | Independent API and workers, managed PostgreSQL, private object storage, keys and operations | Azure planning preference if shared with RealEstateOS; nothing provisioned |
| Optional private local device | Evaluated local inference or future scoped offline cache | Local adapter groundwork; no deployed edge service or replica |
| Existing email accounts | Authoritative mailbox state | Protocol tests only; live enrollment and acceptance pending |

One hosting account does not remove mailbox authorization, identity setup or
separate resource permissions. No database, private mail, keys or live cache goes
in Dropbox. No model, Factory checkout or laptop should be required for hosted
lexical search and synchronization. [Hosting decision](HOSTING_DECISION.md).

## What failures should look like

- **Provider unavailable:** show freshness and bounded retry state; do not claim
  the mailbox is current just because an old search result exists.
- **Unreadable document:** show its receipt/reason and keep usable message evidence.
- **Worker dies or loses permission:** reject stale publication; preserve a
  recoverable job or explicit terminal outcome, not a silent success.
- **Wrong AI interpretation:** retain source evidence, permit correction, and
  eventually supersede the derived claim without rewriting the source.
- **Cloud/model outage:** distinguish search/sync availability from interpretation;
  do not disclose mail to an unapproved fallback.
- **Restore needed:** recover database, external objects and usable keys together,
  then verify hashes, search and authorization. A SQL-only restore is insufficient
  when source bytes live outside SQL.

Some failure mechanisms already have synthetic tests; others are release
requirements. The [coverage matrix](TEST_COVERAGE_MATRIX.md) and exact-commit
[receipts](BUILD_RECEIPT.md) identify which. No count of unit tests replaces
live-provider, cloud disaster-recovery, model-quality or multi-day soak acceptance.

## What the team builds next

First connect the existing PDF worker to explicit durable attachment approval,
immutable results and authorized search, preserving the original body and evidence.
Then finish the secure read-only service: identity, account enrollment, hosted
storage/key recovery, supervision and operational acceptance. State, assistant/team
access and controlled mailbox effects follow their own gates.

[Roadmap](ROADMAP.md) owns milestone order; [backlog](BACKLOG.md) owns work packages;
[Factory handoff](FACTORY_HANDOFF.md) names the next assignment. Open owner decisions
are kept in [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md), not silently turned into consent.
