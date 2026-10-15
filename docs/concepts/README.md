# Concepts and institutional knowledge

Captured 2026-10-15. These guides preserve reasoning, lessons, hypotheses and
tradeoffs. They are explanatory material, not approved specifications, a roadmap,
or evidence that a feature exists. The repository's
[documentation standard](../DOCUMENTATION_STANDARD.md) defines authority.

## Start here

Read [product principles](14_PRODUCT_PRINCIPLES.md),
[invisible intelligence](01_INVISIBLE_INTELLIGENCE.md) and
[knowledge core](02_KNOWLEDGE_CORE.md), then choose a topic below.
Numbers organize the reading path; they are not priority or delivery order.

| Concept | Central idea |
|---|---|
| [Invisible intelligence](01_INVISIBLE_INTELLIGENCE.md) | Make existing tools more useful without requiring every interaction to move into a new application. |
| [Knowledge core](02_KNOWLEDGE_CORE.md) | Preserved evidence and reviewed knowledge serve different purposes. |
| [Email brain](03_EMAIL_BRAIN.md) | Email is one optional source capability within MasterBrain. |
| [Brain folders](04_BRAIN_FOLDERS.md) | A conceptual folder can express an attention view, a query or a proposed command. |
| [Learning and rules](05_LEARNING_AND_RULES.md) | Corrections should become traceable proposals rather than invisible model changes. |
| [Attention and workflow](06_ATTENTION_AND_WORKFLOW.md) | Help an owner decide what needs attention using evidence, deadlines and explicit preferences. |
| [Projects and dossiers](07_PROJECTS_AND_DOSSIERS.md) | A dossier brings together scoped evidence and reviewed assertions about a project while retaining source identity and uncertainty. |
| [Discoveries and weekly review](08_DISCOVERIES_AND_WEEKLY_REVIEW.md) | Periodic review is a proposed way to surface new connections, contradictions and unanswered questions. |
| [Document intelligence](09_DOCUMENT_INTELLIGENCE.md) | Separate preserving bytes, extracting text/layout, identifying statements, reviewing knowledge and executing actions. |
| [Search and retrieval](10_SEARCH_AND_RETRIEVAL.md) | Finding relevant evidence is different from establishing truth. |
| [Model-agnostic access](11_MODEL_AGNOSTIC_API.md) | Keep knowledge and authorization in MasterBrain so different authorized clients can use the same evidence without owning its truth. |
| [Owner control center](12_HTML_CONTROL_CENTER.md) | An owner interface should make evidence, processing state and review choices understandable. |
| [Automation model](13_AUTOMATION_MODEL.md) | Reliable automation needs explicit state, idempotency, retries, cancellation and audit. |
| [Product principles](14_PRODUCT_PRINCIPLES.md) | Preserve evidence, show uncertainty, remain source- and provider-neutral, and make consequential changes reviewable. |

## Provenance and limits

The owner requested this layer after the “Research SaneBox Features” discussion
(ChatGPT conversation ID `6abde7e2-26c8-83e8-a1cc-c06cc3a57a3a`). The supplied
bounded excerpt proposed fourteen themes and named PostgreSQL/pgvector, Docling,
MCP SDK, PydanticAI and Temporal. These guides synthesize that excerpt against the
repository; they do not claim to archive the full conversation or every earlier
lesson. SaneBox-inspired ideas are hypotheses, not newly verified vendor claims.
Add further source material with a clear date and provenance as it becomes available.

The chat's “top five” is not an approved stack. PostgreSQL's role, conditional
pgvector evaluation and existing extraction/API boundaries remain as documented.
PydanticAI and Temporal remain discussion candidates requiring evaluation.
Use [OSS evaluation](../OSS_EVALUATION.md), [tools discussion](../TOOLS_DISCUSSION.md)
and the dated [OSS health observations](../OSS_HEALTH.md) for dependency research;
[pyproject.toml](../../pyproject.toml) and [uv.lock](../../uv.lock) record installed
selections. No upstream versions, licenses, popularity counts or maintenance
measurements were refreshed for this editorial change.

## How an idea becomes work

1. Explore in a GitHub Discussion when available, or an issue/PR discussion.
   Link the source; preserve alternatives and unresolved questions.
2. Distill durable reasoning into a concept guide. Use the common sections here:
   status/date, idea and lesson, illustrative use, boundaries/next evidence and
   canonical follow-through. Mark adopted, deferred or rejected ideas explicitly
   and link their decision; keep useful rejected rationale rather than erasing it.
3. Record owner decisions still needed in [open questions](../OPEN_QUESTIONS.md).
   Change the [PRD](../PRD.md) only for approved requirements. Record architectural
   decisions through the existing [ADR index](../DECISIONS.md) and `docs/adr/`
   conventions, before implementation where AGENTS.md requires it.
4. Update architecture/data model/contracts as applicable. Put delivery scope and
   acceptance in an issue and existing roadmap/backlog; verify through the normal
   contributor and release process. Keep current status and exact-commit receipts
   separate from concept prose.

A discussion, concept or RFC cannot approve itself. When a concept conflicts with
an applicable accepted ADR or security invariant, flag the conflict and follow the
existing decision process rather than treating the concept as a newer authority.
This directory contains project documentation, not runtime user memory or a place
for real mail, private attachments, secrets or production knowledge records.

## When to introduce RFCs

No RFC directory, numbering scheme, template or approval process is introduced.
Use a focused issue/PR and a concept guide for ordinary exploration, then the
existing ADR process for decisions. Introduce a lightweight RFC convention only
when a substantial unresolved proposal needs coordinated review across components,
competing alternatives, migration/compatibility analysis or several owners before
an ADR can be decided. Examples include replacing the workflow engine or adopting
a cross-source learning policy. Complexity and review need, not every new idea,
should trigger it.

Agree the RFC location, owner, status lifecycle and review/decision criteria in a
reviewed documentation change when that need arises. Link the eventual ADR and
update canonical contracts; an RFC remains a proposal and never substitutes for
required architecture/security approval or implementation evidence.

## Maintenance

Update a guide when its rationale changes or a linked decision settles an open
choice. Keep one canonical owner for each fact and link to it; do not copy status
inventories or OSS metrics here. Review links, status language, source provenance
and privacy in the same PR. Follow the
[contributor guide](../../CONTRIBUTING.md) and run the existing documentation gate.
