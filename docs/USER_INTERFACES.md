# MasterBrain user interfaces and controlled actions

Status: product target. A first-party read-only, conversation-shaped search
workspace and a provider-neutral external read client now exist. The default
local extractive path returns server-verified source quotes; it can be explicitly
disabled. ADR-146 also shows separately labelled, bounded reviewed KnowledgeCore
matches with direct evidence links. These matches are interpretations, not source
quotes or an AI answer. Freeform synthesis, certified assistant
integration, hosting and source-write capability do not exist. [Current functions](CURRENT_FUNCTIONS.md) and
[implementation status](IMPLEMENTATION_STATUS.md) describe executable behavior.
Synthetic bootstrap and verified administrator-bound OIDC Brain assistants
using the reviewed Brain search, evidence and status routes require explicit
source enrollment (ADR-133/142).
OIDC grant removal invalidates saved contexts at the next transaction; hosted
issuer enrollment and derived-cache revocation are still
open ([issue #88](https://github.com/jbone3311/MasterBrain/issues/88)).
ADR-149 excludes assistants from unfenced legacy Email compatibility routes;
their Email reads use source-enrolled Brain routes.
ADR-150 adds an explicit All/Email/FileOS focus in `/brain` and the external
read client. A focused request skips excluded source reads, labels unsearched
groups and leaves access grants unchanged. It is not automatic intent routing.
ADR-163 adds an in-review, explicit project-dossier drill-down from a reviewed
project match in either Ask or Search only. It calls the same scoped read API,
shows a bounded set of linked reviewed events and commitments with evidence
controls, and labels project state as an assertion rather than current truth.
No project fetch occurs until the owner opens it.
ADR-164 adds an in-review, explicit Reviewed schedule panel: the owner selects
a UTC date window, then separately requests occurrence-dated reviewed events
or due-dated reviewed commitments. It uses the existing scoped Brain API,
shows one ten-item page with an explicit continuation and evidence controls,
and excludes undated assertions. It is not automatic chat intent routing,
source freshness or an inferred current status.

## One service, two entrances

MasterBrain should let its owner ask questions and find Email, files and
KnowledgeCore facts in a first-party conversational workspace. Approved external
assistants (for example Grok, Claude or ChatGPT) should be able to do the same
through the versioned Brain API or a thin, tested client adapter. Both entrances
must use the same tenant/source grants, retrieval functions, freshness rules,
evidence citations, budgets and audit policy. Neither connects directly to
PostgreSQL, object storage, a mail provider or an unrestricted filesystem tool.

The first-party interface may offer search forms and evidence drill-down even
without an LLM. A model may translate a question into bounded API calls and
synthesize a cited answer, but it does not become the system of record. Examples:
“find the invoice email and its attachment,” “which file has the latest proposal?”
and “what commitments changed this week?” A result must show what source was
searched, what was not covered, when it was observed, and how to inspect the
original evidence. Search, answer synthesis and a source action are distinct
operations, not interchangeable responses to a chat message.

## Access modes

| Mode | Permitted behavior | Excluded behavior |
|---|---|---|
| Read-only | Scoped search, compact results, selected expansion and separately scoped original-evidence access | Source changes, raw database access, hidden broad corpus export |
| Propose | Typed, bounded Email/FileOS change request and deterministic preview | Executing the change or granting itself approval |
| Execute | A separate, least-privilege worker applies an approved, still-current command and records a receipt | Arbitrary model-authored shell, SQL, provider calls or paths |

Read-only is the first hosted release. Write/action mode is opt-in per identity,
source, operation and target; it is not a universal “read-write API key.” Early
candidates might include a reversible file rename/move or an Email label change.
Sending mail, permanent deletion, bulk organization and cross-root movement need
their own later design and explicit authorization; they are not implied by this
contract or by FOS-Master parity.

For an action, the service validates the current identity and target, presents
the exact before/after and affected-item count, applies policy and required human
approval, then hands an idempotent command to a narrowly scoped executor. It
rechecks the source version and authority immediately before execution, records
success/failure per item, reconciles partial work, and offers a documented undo or
quarantine path where the source permits one. Denied, stale, over-broad or
unrecoverable requests fail closed. Prompt text and retrieved content cannot
approve an action or widen a grant.

## Hosted and local boundaries

A central private MasterBrain service can hold the authoritative PostgreSQL
database, encrypted retained evidence, indexes and API so multiple authorized
clients see the same state. External AIs connect only to its authenticated API;
the database is not exposed as their tool. File roots may remain on an owner's
machine or private storage. A narrowly enrolled local FileOS agent/scanner reads
only approved roots and later performs only approved effects. The hosted API
must not gain blanket access to the owner's machine. Email connectors likewise
keep provider credentials in dedicated least-privilege services. Hosting region,
budget, retention, identity provider, source enrollment and backup/restore
require owner decisions and live acceptance before production use.

Conversation history is not evidence. It has its own retention, deletion and
access policy; source content and secrets do not go into application logs or
model-visible tool definitions. A revoked source grant must remove access from
search, evidence expansion, caches, summaries and future chat turns. Models are
optional and provider-neutral; they must not receive source or database
credentials.

## Build order and acceptance

1. **Common read contract:** make Email, FileOS and KnowledgeCore retrieval
   source-current, bounded and citation-bearing; expose explicit partial
   coverage/freshness. Prove denial and revocation, including derived caches.
2. **First-party workspace:** a read-only question screen now groups current
   search and separately authorized evidence expansion without a model. It can
   now request verified extractive quotes through ADR-134/144. ADR-145 removes
   fixed question boilerplate from Ask retrieval without semantic rewriting;
   a question still needs distinctive source words. An explicitly
   disabled selector falls back to grouped search; an explicit Search only control
   remains available to search-only credentials. ADR-146 lists source-scoped
   reviewed assertions separately and rechecks them before disclosure. True synthesized conversation
   remains gated on further grounded-answer and prompt-injection acceptance.
   ADR-150 lets the owner explicitly focus either mode on Email or FileOS;
   changing focus invalidates an in-flight result, and the page does not claim
   excluded groups were searched.
   ADR-151 caps selector-visible source text by UTF-8 bytes and visibly warns
   when an upstream character or byte cap shortened that context; a no-quote answer under that warning is
   not evidence that the rest of the indexed source text was considered.
   ADR-157 separately bounds returned untrusted quote and reviewed-match text,
   keeping exact citations while visibly flagging shortened reviewed display
   text. It does not make Ask a complete AI-written conversation.
   ADR-163's explicit project control reuses ADR-162's exact-project read with
   fixed five-item linked lists and separate evidence drill-down. It remains
   read-only and is not a project-state reducer or live-source proof.
   ADR-164's separate schedule controls reuse ADR-160/161's source-aware
   date-window reads; editing the window clears an in-flight schedule page.
3. **External client:** a provider-neutral reference client now runs the same
   fictional current-search and evidence calls as the owner workspace, with
   source/scope parity tests. Next connect at least one separately authorized
   assistant through a thin adapter; prove prompt-injection isolation,
   revocation, citations, budgets and source freshness, not prose wording.
4. **Hosted read-only pilot:** establish owner-approved private storage, identity,
   enrollment, operations, content-safe telemetry, backup/restore and a bounded
   live-source trial. A green synthetic test is not a production acceptance.
5. **Reviewed effects:** begin with one reversible FileOS action and one narrow
   Email action only after new ADRs, threat models, source-specific parity,
   preview/approval/expiry/idempotency/failure/rollback tests and owner sign-off.
   Verify that a read-only client cannot even propose execution and that a
   proposal cannot execute without the independent grant and approval.

The acceptance scenario is: the owner asks in MasterBrain chat and an approved
external assistant asks through the API for the same email, file and related
fact. Both receive current, permission-consistent evidence with working
drill-down and visible gaps. A read-only identity cannot alter either source.
An authorized, reviewed rename/label request shows exact effects before acting,
is safe to retry, produces an audit receipt, and has a demonstrated recovery
path. FOS-Master remains unchanged until separate FileOS parity and cutover
gates pass.
