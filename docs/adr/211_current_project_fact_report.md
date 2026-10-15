# ADR-211 — Current-source project fact report, without numeric aggregation

Status: implemented for fictional, read-only testing on an open PR; hosted
exact-head and merged-main gates remain required. No live-source permission,
investment truth claim or FOS-Master cutover follows.

## Context

[ADR-209/210](210_fos_entity_money_report_baseline.md) compare the five FOS
donor report row shapes, but the donor `dollars_by_domain` sum mixes money facts
without currency, ownership, duplication or review context. MasterBrain
already has [ADR-195](195_source_stated_project_facts.md) source-stated,
reviewed project facts. Its read checks project grants and every fact evidence
item's current version, active source, Email exclusion, source enrollment and
quote presence **before** pagination. That is the safe substrate for a first
product report; donor raw fact rows are not.

## Decision

Expose `GET /v1/knowledge/projects/{project_id}/facts/report` under the same
`knowledge.search` and assistant source-enrollment policy as the existing fact
page. Reuse that page within one tenant-fenced read transaction and group only
its visible 1–25 compact facts by predicate. Preserve each fact's own status,
preview, evidence IDs, quote basis, observation time and cutoff. Report whether
different **asserted previews on this page** are present and whether a
disputed/retracted row occurs. Mark each comparison incomplete if there is a
continuation page, a prior cursor or a truncated asserted value. These are
review-navigation signals, not contradiction or current-truth decisions.

Return an explicit `numeric_aggregation=none_units_currency_ownership_unverified`
and `interpretation=reviewed_source_statements_not_investment_truth`. Do not
sum amounts, turn `number` values into balances, fetch source bytes or create
source effects. Return no hidden-source counts or invented citations. The
provider-neutral client validates the complete report envelope, every compact
fact and the page-local flags before passing content to an LLM.

## Acceptance and next gates

Use fictional PostgreSQL evidence to prove hidden-before-limit paging,
source-enrolled assistant allow/deny, stale-version refusal, closed query
limits, no-store responses, and client rejection of a forged investment-total
label. A pure test proves grouping, page/truncation warnings and absence of a
total. This is a page-local orientation report, not a complete dossier: a
future financial report requires complete predicate coverage beyond
[ADR-214's](214_project_fact_predicate_catalog.md) first project-fact catalog,
[ADR-212's](212_exact_project_fact_measurement.md)
opt-in exact decimal units/currencies plus complete coverage, ownership,
deduplication, source-tier attestation, conflict
review and a known-answer cross-source company corpus. The current source
check is performed per request; the recorded cutoff is not a durable snapshot
across pages. Rollback removes this route and projection without changing
persisted facts, existing APIs or FOS-Master.
