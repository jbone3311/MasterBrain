# Keeping the product documentation accurate

Updated 2026-09-21. Maintenance convention for this repository; no runtime,
permission, deployment or Factory-policy change.

## One place owns each kind of truth

| Question | Primary record |
|---|---|
| What should the ultimate product do? | [PRD](PRD.md) |
| How does it work for an owner? | [Worked walkthrough](PRODUCT_WALKTHROUGH.md), [features/methods](FEATURES_AND_METHODS.md), [methods guide](METHODS_GUIDE.md) |
| What is executable now? | [Current functions](CURRENT_FUNCTIONS.md), [implementation status](IMPLEMENTATION_STATUS.md), linked source/contracts |
| What passed, at which revision? | [Build receipt](BUILD_RECEIPT.md), linked exact-commit CI/restore runs |
| What comes next and why? | [Roadmap](ROADMAP.md), [Email backlog](BACKLOG.md), [Factory handoff](FACTORY_HANDOFF.md) |
| How should changes be contributed and accepted? | [Contributor guide](../CONTRIBUTING.md), [release acceptance](RELEASE_ACCEPTANCE.md) |
| What ideas and lessons informed the design? | [Concepts and institutional knowledge](concepts/README.md), with linked source discussions |
| What are the canonical component boundaries and schemas? | [Architecture](ARCHITECTURE.md), [data model](DATA_MODEL.md), applicable accepted ADRs |
| Why was a boundary chosen? | [Accepted decisions](DECISIONS.md) and applicable ADR |
| What still needs the owner? | [Open questions](OPEN_QUESTIONS.md) |
| How healthy was an external dependency when inspected? | [OSS health](OSS_HEALTH.md), with its actual measurement date |

Security invariants and applicable accepted ADRs govern behavior. Source and tests
show the implementation; a contradiction with an approved contract is a defect to
resolve, not permission to silently change the contract. Do not use a newer prose
date to override an older exact-commit verification result.

## Concepts, discussions and decisions

[Concepts](concepts/README.md) preserve institutional reasoning, hypotheses,
examples, alternatives and lessons. They explain why an idea may matter; they do
not own product requirements, architecture, data schemas, adoption decisions or
current capability status. Mark exploratory material explicitly and link to the
canonical documents rather than duplicating their inventories.

Use discussion or an issue/PR to explore, distill enduring rationale into a concept,
then update PRD requirements or record the applicable ADR when a decision is made.
Architecture and data model remain canonical for their boundaries; accepted ADRs
retain their existing precedence and history. Follow the contributor process for
scoped implementation, tests, status and exact-commit evidence. Concepts cannot
waive security, authorize live sources or create delivery commitments.

Use the guide's common structure: status/date and provenance, idea/lesson,
illustrative example, boundaries/next evidence, and canonical follow-through.
Retain rejected/deferred rationale with linked decisions; put unresolved owner
choices in OPEN_QUESTIONS.md. Keep real user knowledge and private evidence out of
this source-controlled documentation layer.

No RFC system is needed for this addition. Introduce one only when a substantial
unresolved cross-component proposal needs coordinated review of alternatives,
compatibility or migration before an ADR can be decided. Agree its ownership,
location, lifecycle and decision criteria in a reviewed documentation change at
that point. An RFC would remain a proposal, not replace required ADRs. See the
[full promotion and RFC guidance](concepts/README.md#when-to-introduce-rfcs).

## Status vocabulary

- **Planned:** a requirement/design, not a callable capability.
- **Groundwork / offline contract:** a component exists, but the user workflow or
  live integration is incomplete. Name the missing connection explicitly.
- **Implemented prototype:** executable within stated synthetic/local/CI limits.
- **Verified at commit:** specific checks passed at the linked revision. Report
  skips and warnings; separate mocks, real SQL, actual containers and browser tests.
- **Live accepted / production released:** use only with explicit authorization,
  environment-specific acceptance, operational ownership and recorded evidence.

Do not collapse imported, preserved, searchable, extracted, scanned, interpreted,
approved and executed into “processed.” Do not call proposed schemas existing
tables, proposed MCP tools registered tools, or generic proposal approval execution.

## Update checklist for every feature change

1. Classify the change; write the required ADR before a new schema, integration,
   API, workflow, permission or security behavior.
2. Update the implementation contract and tests alongside code/migrations.
3. Update status, feature/method explanation, code map and changelog. Adjust PRD
   only when requirements change; do not turn current limitations into the vision.
4. Update roadmap/backlog/handoff so the next assignment does not rebuild a finished
   component. Explain prerequisites, acceptance evidence and remaining gaps.
5. Update deployment/runbook notes for configuration, telemetry, upgrade sequencing,
   cancellation, rollback/forward repair and restore implications.
6. Record actual validation with exact commit and environment. Keep old receipts;
   do not overwrite historical counts or claim a later docs commit was the runtime
   revision tested earlier.
7. Check local links and required files, inspect the rendered GitHub reading path,
   and review for secrets/real mail before publishing.

## Automated check scope

Run the repository checks in [AGENTS.md](../AGENTS.md). Under
[ADR-037](adr/037_documentation_verification.md), `scripts/check_docs.py` requires
the original 16 pack files, product/contributor/release/operator guides and GitHub
issue/PR templates. It reads root Markdown and all Markdown in `docs/` and `.github/`.

It checks inline-link/reference-definition destinations, repository-contained
paths, same-document/cross-document heading fragments, encoded paths/fragments,
duplicate heading IDs and the explicit anchors used by this pack. Fenced examples,
inline code, comments and template frontmatter are excluded. This repository's
explicit `blob/main` documentation URLs are resolved against the checkout, which
catches template navigation errors without a network request. That is not proof
the checkout has been pushed to GitHub.

The checker implements a limited Markdown subset, not a full GitHub renderer.
Complex/nested inline markup, all reference-use syntax, HTML navigation and every
GitHub extension are not certified. It does not check external URL availability,
factual accuracy, source freshness, image layout or rendered accessibility. Those
require separate review; a green check alone is not proof every claim is correct.
Synthetic regression tests are in [test_check_docs.py](../tests/test_check_docs.py).

## Research and citations

Link primary sources adjacent to technical claims. Mark community experiences as
anecdotes rather than benchmarks. For external packages, retain license/version,
maintenance measurement date, actual metrics and reuse-versus-pattern rationale.
Recheck volatile prices, plans, model availability and API behavior before adopting
them. Updating our docs does not mean every external project was rescanned.

The 2026-09-21 documentation review rechecked PostgreSQL RLS, pgvector's retrieval
options, Azure Container Apps overview and official MCP security guidance. It did
not refresh OSS popularity/activity counts, obtain a cloud quote or certify any
assistant client. References remain beside the relevant architecture/interface
claims. Source-only downloads must exclude credentials, environments, private data,
logs and database/object backups.

The follow-up consistency pass preserves original OSS/research observations and
historical receipts, aligns ADR-035/036's current PDF/operator descriptions, adds
the methods guide and expands the offline navigation/inventory gate with tests.
No application runtime, schema, dependency, permission or hosting decision changes.

ADR-038 subsequently adds the owner PDF screen and its separate workflow guide.
The current product/status/roadmap pages now distinguish that implemented UI from
pending browser accessibility, live-document policy and hosted acceptance. Its
verification receipt also records the SQL-to-UI scan-status mismatch and correction;
passing hand-authored UI fixtures alone was not sufficient acceptance.

The post-ADR-039 editorial pass adds a one-minute product map and aligns the
landing pages, game plan, roadmap, backlog and Factory assignment on identity as
the next build package. Completed read/PDF operator and owner workflows stay
marked implemented; browser/live/hosted gates stay open. The old EB-006 section
anchor remains valid for existing links. This pass changes documentation only,
does not implement authentication and does not refresh external research counts.

ADR-040 subsequently adds the actual API token/mapping boundary and its required
[identity guide](IDENTITY_AUTH.md). Product/status/roadmap/handoff now distinguish
that implemented foundation from browser login, issuer policy/enrollment and team
grants. Only PyJWT receives a new focused maintenance/license/advisory observation;
the prior OSS tables keep their original dates. Runtime claims require the new
exact-commit SQL/container/restore receipts, not the earlier documentation CI run.
