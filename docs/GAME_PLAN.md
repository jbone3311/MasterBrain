# Email Brain: the game plan

Updated 2026-09-21. Product direction, not a claim that all features are available.
[Implementation status](IMPLEMENTATION_STATUS.md) and the exact-commit
[build receipt](BUILD_RECEIPT.md) define current evidence.

## The finished experience

For a concrete example, read the [Melron product walkthrough](PRODUCT_WALKTHROUGH.md).
It explains each user-visible step, the method underneath and its current status.

Email Brain maintains a searchable, evidence-backed view of authorized mail. It
knows which conversations relate to a project, which requests remain open and
where a fact came from. An assistant gets compact cited context instead of having
to reread hundreds of messages for each question.

Assistants can send information back: “Create a Melron project,” “This sender
matters,” or “I need a new capability.” These become typed proposals. Rules and
knowledge change through policy/review; software changes go to Factory. Instructions
embedded in mail are source text, never authority.

The service must keep operating when Jim's laptop, a model or Factory is offline.
Hosted search/sync cannot depend on local inference. Deferred interpretation stays
visible rather than silently escalating to a remote model.

## Product promises

1. Find messages and supported attachments with exact evidence-version citations.
2. Derive needs-reply, waiting-on, deadlines and project state with uncertainty and corrections.
3. Turn repeated accepted judgments into reviewed rules that code can apply cheaply.
4. Preview changes; organize virtually before adding separately authorized mailbox effects.
5. Account for held messages and unsupported attachments. Sync progress is not extraction completeness.
6. Prove replay, recovery and restore; preserve audit and hashes.

## Example: a deal develops over email

A fictional broker sends a property PDF and Excel rent roll. Every source and
attachment gets a receipt. A later message corrects the spreadsheet; old and new
versions remain distinguishable. The assistant answers “what are we missing?” from
current evidence, naming unprocessed documents and uncertain claims. An owner
correction updates derived state, not the original email. Filing or drafting needs
its own permission and review.

**Today:** synthetic ingestion, receipts, FTS, proposal review and narrow virtual
rules work. Restricted PDF processing now has a synthetic approval API/library,
immutable results and opt-in search. Its owner UI/CLI, live/scanner policy,
automatic project state and mailbox actions remain planned.
[Features and methods](FEATURES_AND_METHODS.md).

## What the owner will actually use

- **Ask:** find a message, document or current project question and receive bounded
  evidence, not an unsupported answer or an entire mailbox pasted into a model.
- **Review:** see what needs attention, what was deferred, what a proposed rule
  would change and why. Accept, narrow or reject without modifying original mail.
- **Teach:** confirm a relationship or repeated preference. The service records a
  proposal and its outcome; it does not assume every casual remark is permission.
- **Operate:** see account freshness, held items, processing failures and recovery
  health. An offline model must not stop ingestion or lexical search.

The present local UI covers search, evidence, proposals, narrow rules and recovery.
It is not yet a complete project dashboard, assistant connection or hosted inbox.

## The immediate implementation gap

Attachment accounting and attachment understanding are separate milestones. We
already know a PDF arrived and can preserve it. We cannot yet extract/index its
text in production. Existing processing approvals refer to quarantined **messages**;
they are not general permission to process every deferred attachment.

ADR-035 now supports that ordinary searchable email through a separate synthetic
document approval API/library. It binds source/part/processor identity and preserves
the body index, then saves immutable extraction evidence for opt-in search. Next
complete the owner/operator interface and accepted live/scanner policy. Scanning,
extraction and OCR remain distinct outcomes and acceptance gates.

## Build sequence

| Milestone | Outcome | Reason for order |
|---|---|---|
| Foundation | Synthetic inbox -> evidence -> search -> review -> restore | Prove consistency and isolation before private data |
| Read-only pilot | One enrolled provider, production identity/storage, supervised processing, alerts and disposable-mailbox acceptance | Turn libraries into an independent service |
| Understanding | Safe document extraction, richer rules, evaluated local candidates and people/project/obligation state | Interpretation needs trustworthy source coverage |
| Assistant/team access | Narrow authenticated MCP, resource grants and revocation | Prevent broad assistant or shared-account exposure |
| Controlled effects | Previewed labels/moves/drafts with outbox and reconciliation | Do not let uncertain interpretation mutate mail |
| Expansion | More providers, measured hybrid search, approved remote inference, optional cache | Add infrastructure when the baseline shows a need |

These are dependencies, not dates. Contract tests can run in parallel, but no
milestone bypasses security/live gates. [Roadmap](ROADMAP.md) defines exits;
[backlog](BACKLOG.md) names work packages.

## Hosting and independence

Preferred planning home: Azure alongside RealEstateOS billing, not inside its
application. Separate deployment, identities, database and object permissions.
Managed PostgreSQL is shared authority; Blob holds larger encrypted source objects.
API and workers have different privileges. SQLite is an optional future local
cache, not a multi-writer database in Dropbox.

Python/PostgreSQL and explicit provider/model/storage interfaces preserve an exit
path. Azure does not force Microsoft mail or models. No cloud resources are
provisioned. Region, budget, identity, retention and first account remain
[owner choices](OPEN_QUESTIONS.md).

## Test strategy and release bar

- Known-answer fictional scenarios: real file bytes, coherent messages, repeatable
  randomness and expected extraction/classification/state without real PII.
- Failure/security pressure: crashes, lost responses, foreign IDs, revoked access,
  malformed MIME, corrupt storage and missing restore objects.
- Explicit acceptance: disposable providers, actual restricted processors,
  production-like identity, accessibility, measured models and multi-day soak.

Public collections supplement specific parser gaps only after rights/safety review.
They are not a random-mail subscription. See [test mailbox plan](TEST_MAILBOX_PLAN.md).

No live release until selected-provider, identity, keys, scanner/processing policy,
backup/restore, retention and incident ownership are accepted. Unsupported files
stay visibly deferred. Report retrieval quality, review precision, abstention,
cost and latency with sample size and versions—not just test counts.

No automatic sending or permanent deletion in the initial product. Factory's
independent audit remains a gate; this repository cannot certify its own Factory bind.
