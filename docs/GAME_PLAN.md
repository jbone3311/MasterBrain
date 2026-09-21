# Email Brain: the game plan

Updated 2026-09-21. Product direction, not a claim that all features are available.
[Implementation status](IMPLEMENTATION_STATUS.md) and the exact-commit
[build receipt](BUILD_RECEIPT.md) define current evidence.

## The finished experience

For a concrete example, read the [Melron product walkthrough](PRODUCT_WALKTHROUGH.md).
It explains each user-visible step, the method underneath and its current status.
The [methods guide](METHODS_GUIDE.md) translates checkpoints, evidence, leases,
search, rules and permissions into their practical purpose.

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
immutable results, opt-in search, a separate operator command and owner review UI. Live/scanner policy,
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

## What is decided, and what remains optional

- **Keep:** Python service plus separate workers, PostgreSQL authority, immutable
  evidence, tenant isolation, code-first handling and narrow provider/model adapters.
- **Build first:** a dependable read-only search/evidence service, with visible
  document limitations and recovery, before adding automatic understanding/actions.
- **Preferred hosting:** one approved Azure billing home if that is the existing
  RealEstateOS choice; independent Email Brain resources and permissions.
- **Evaluate later:** local model/version, vectors, OCR/Office readers, remote-model
  disclosure and any separate graph/search infrastructure. Popularity is not acceptance.
- **Owner decisions still parked:** first account/backfill, region/budget, retention,
  sharing and live-document policy. None prevents safe synthetic implementation.

This is not a replacement mail server or a new all-purpose agent platform. SMTP
does not import mail. Connectors read provider changes; a future separately approved
executor would handle provider drafts/filing. Factory builds and audits the product,
but is not in the deployed request or processing path.

## The immediate implementation gap: identity and independent operation

The optional [browser session backend](BROWSER_AUTH.md) now handles code/PKCE,
opaque cookies, CSRF and current mapping checks. Next integrate it with private
operator/TLS startup and the owner screen, then verify real browser behavior.
Default startup and UI still use the earlier explicit credential modes.

[ADR-040](IDENTITY_AUTH.md) now verifies configured access tokens, maps identity
to existing server-controlled access and rechecks current permissions when data is
used. Unknown identities cannot create tenants or grant themselves access. Next
build the browser sign-in/session lifecycle; manual access-token entry and the
local bootstrap file are not a completed remote sign-in experience.

After that foundation, complete hosted storage/key recovery, supervised workers,
enrollment administration and alerts. Browser/document-policy acceptance and a
disposable-provider pilot are separate proofs. The [roadmap](ROADMAP.md#next-build-packages)
and [Factory assignment](FACTORY_HANDOFF.md#suggested-next-issue) define this order.
No account registration, hosting purchase or real-mail connection follows merely
from approving the product plan.

### Attachment coverage is still a release gate

Attachment accounting and attachment understanding are separate milestones. We
already know a PDF arrived and can preserve it. We cannot yet extract/index its
text in production. MIME recovery approvals refer to quarantined **messages**;
they are not general permission to process every deferred attachment.

ADR-035 now supports that ordinary searchable email through a separate synthetic
document approval API/library. It binds source/part/processor identity and preserves
the body index, then saves immutable extraction evidence for opt-in search. Next
complete accepted live/scanner policy and hosted/browser acceptance. Scanning,
extraction and OCR remain distinct outcomes and acceptance gates.

ADR-038 now lets an owner select one eligible PDF, see the exact processor/policy,
explicitly approve it, inspect/cancel the job, then find its cited text. ADR-036
supplies the separate operator command with its own worker identity. No automatic
approval, new mailbox scopes or API access to the container daemon is added.
The [owner guide](DOCUMENT_REVIEW_SCREEN.md) explains this synthetic workflow and
remaining browser/live gates; the team should not rebuild the completed backend/UI.

## Build sequence

### Reuse the completed synthetic owner workflow

The implemented owner-visible path is: find a synthetic message, select its eligible PDF,
see the exact processor/policy and explicitly approve it, inspect or cancel the
job, then read cited page excerpts and opt into document search. Preserve the
working body result throughout. The approval API, restricted reader, storage/search,
separate operator command and review UI now exist; do not build them again.

Acceptance must include permission/source changes, lost responses and same-intent
retry, cancellation races, stale screens, partial/deferred extraction and default
search behavior—not only a successful PDF. Node and SQL/API-response contracts
exercise these boundaries; browser/keyboard/screen-reader acceptance remains.
ADR-039 now adds the [bounded read-worker operator entry point](READ_CONTROLLER.md).
ADR-040 supplies the API identity boundary. Next build browser/session lifecycle,
then complete operational visibility/
supervision and production storage. The
command does not enroll accounts, reset pauses or authorize real-mail access,
automatic approval or paid deployment.

### From prototype to independent product

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
The [release acceptance guide](RELEASE_ACCEPTANCE.md) turns these gates into a
reviewable evidence record. Questions and approvals remain visible, not silently
treated as answered when implementation progresses.
