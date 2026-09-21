# Executive architecture review

Updated 2026-09-21. Start with [GAME_PLAN.md](GAME_PLAN.md) and
[FEATURES_AND_METHODS.md](FEATURES_AND_METHODS.md) for the owner narrative.
The architecture verdict below is not a production-readiness certificate.

## Verdict

The product is worth building. Its strongest form is **an independent, evidence-first
email service governed by Factory**, not a mail-reading chatbot and not a Factory
runtime plugin. PostgreSQL is shared authority; provider mailboxes remain authority
for mailbox state. Code handles repetition; models interpret only bounded ambiguity.

The ultimate product continuously maintains authorized people, companies, projects,
threads, obligations, waiting-on state, decisions, and retained attachments. An
assistant asks for compact cited context, proposes a new Melron project or rule,
and gets a tracked result. Human review, version history, previews, and reversible
effects make this feedback loop useful without permitting self-modifying automation.

## Architecture refinements from the review

| Gap | Refined decision |
|---|---|
| Multi-user versus “one owner with many accounts” | Tenant foundation now; owner-only bootstrap; membership/account/project grants and invitation/revocation before team use |
| Dropbox could accidentally become runtime storage | Code/content surface only; no live Postgres, venv, secrets, model caches, SQLite or embeddings in Dropbox |
| Hosting could depend on Jim's Mac/Factory | Independent hosted API/worker/database; edge inference optional, outbound-only, durable pending jobs while offline |
| SQL relationships could cross tenants/accounts | Composite ownership foreign keys plus forced RLS, runtime-role and negative tests |
| Search might reveal data before final filtering | Apply authorization before every lexical/vector candidate query and cached result; post-filtering is not the boundary |
| Historical citations might point at changed text | Immutable normalized version records and evidence IDs; retain parser/hash provenance |
| “Immutable” could accidentally mean never deletable | Immutable while retained; explicitly authorized retention/purge path covers blobs, projections, vectors, replicas and backup aging |
| Attachments could disappear on failed extraction | Receipt + append-only event for each part; clear pending/deferred/failed/skipped outcomes; reconciliation must balance |
| Held-message recovery might be mistaken for general document processing | Ready mail with deferred attachments needs a source/part-bound approval and result path; preserve working body search and keep scanning separate from extraction |
| Model confidence could authorize effects | Claimed confidence is telemetry; measured calibration, consequence and explicit policy govern review |
| Moving a message might train the wrong rule | Explicit corrections outrank weak behavioral signals; distinguish user moves from our own writes; decay/review learned rules |
| An approved proposal could execute unexpectedly | Review status separate from apply/action status; approval binds exact payload/version/expiry in the future executor |
| Mailbox retries could send/move twice | Inbox/outbox, idempotent keys, expected provider state, and ambiguous-result reconciliation; never promise universal exactly-once provider effects |
| “MCP compatible” might overpromise | REST first; verify OAuth/tool support and deployment reachability separately for Grok/ChatGPT/Claude |
| Provider thread IDs could imply global threads | Preserve provider/account-scoped IDs; canonical cross-account thread links are versioned, evidence-backed, reversible hypotheses |
| Factory has overlapping historical conventions | Follow current bind contract for development; stage package/standards gaps for Factory, never silently copy governance |

## Build order and launch bar

1. Prove synthetic ingestion → Postgres → FTS/evidence → review, including replay,
   RLS and attachment accounting. This prototype implements that bounded slice.
2. Complete one read-only connector, durable poison-message quarantine, encrypted
   objects, reconciliation and backup restore. Fastmail JMAP is the provisional
   engineering default, not a claim Jim's first account is enrolled.
3. Add OIDC, owner review UX, rate limits, audit export, attachment sandbox/scanner
   and operational health. Ship no Internet-facing service before these gates.
4. Expand the implemented narrow reviewed virtual rules; calibrate local extraction
   on approved labeled data. Add people/projects/obligations as evidence-backed projections.
5. Add scoped assistant/team access with production authorization and independently
   verified MCP client support; tenant RLS alone is not shared-account authorization.
6. Add previewed labels/moves/drafts with a separate executor; prove compensation
   limits and ambiguous-result handling before production effects.
7. Expand providers, evaluated hybrid vectors and approved
   remote escalation. Avoid graph infrastructure unless relational limits are measured.

Not yet production-ready: live sync, provider enrollment, integrated document
extraction/search, OIDC, full team grants, production backup/purge and authenticated MCP
remain unfinished. See [status](IMPLEMENTATION_STATUS.md), [backlog](BACKLOG.md),
[hosting recommendation](HOSTING_DECISION.md), and [open choices](OPEN_QUESTIONS.md).

The restricted PDF worker now has a synthetic approval/result/search API/library,
not a completed owner UI or live deployment. The [owner walkthrough](PRODUCT_WALKTHROUGH.md) makes this and
the other current-versus-target boundaries explicit for the team.

The detailed delivery sequence is maintained in [ROADMAP.md](ROADMAP.md): secure
read-only operation, useful understanding, scoped assistant/team access, then
separately approved mailbox effects. No new effect is authorized by this review.

## Success is measured, not inferred

Retain the PRD targets but label them targets: retrieval top-5 ≥90%, Needs Reply
precision ≥95%, Review Delete precision ≥99.5%, ≥70% no-remote processing, zero
unauthorized tenant reads, and 100% valid evidence references. Report sample size,
confidence intervals, abstention, false-negative rates and per-provider slices.
Production SLO/RPO/RTO are commitments only after measured load/restore drills.

Sources underpinning the refinements: [Postgres RLS](https://www.postgresql.org/docs/17/ddl-rowsecurity.html),
[JMAP mail](https://www.rfc-editor.org/rfc/rfc8621),
[OWASP injection defenses](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html),
[Factory intake review](FACTORY_INTAKE_REVIEW.md).
