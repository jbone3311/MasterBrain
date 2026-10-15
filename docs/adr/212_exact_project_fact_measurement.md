# ADR-212 — Opt-in exact-decimal measurement on reviewed project facts

Status: implemented for fictional testing on an open PR; hosted exact-head,
independent restore and merged-main gates remain required. No live source,
portfolio balance, FX calculation or FOS-Master cutover is authorized.

## Context

ADR-211's source-granted project fact report cannot safely aggregate the
existing `number`-typed `value` strings. They carry no unit, currency or owner
semantics. Parsing every historical value would invent meaning. The FOS donor
`dollars_by_domain` is a raw money-fact sum, not an investment balance.

## Decision

Add nullable `amount_decimal numeric(30,8)`, `unit_code` and `currency_code`
to immutable `knowledge_project_facts` through additive migration 0071. Old
rows remain NULL and are never inferred or rewritten. A new human-reviewed
`ProjectFactWrite.measurement` is an optional closed object with a **string**
decimal (no float/scientific notation; at most 22 integer and eight fraction
digits), one of `currency`, `shares`, `percent`, `count`, and a three-uppercase-
letter currency code only for currency. The code is a lexical identifier,
not an ISO-registry or FX-rate certification. `value_type` must be `number`,
and the fact's full `value` must be the same decimal string.

The amount and unit/currency token must occur in the exact `source_quote`,
which the existing current-evidence publication path verifies against the
normalized source text. Migration 0071 originally used a literal substring
check; [ADR-213](213_project_fact_measurement_quote_tokens.md) adds complete
lexical token boundaries in migration 0072. Neither is a general
numeric parser: it does not prove scale, ownership, whether a figure is a
balance versus transaction, or that the source itself is correct. SQL checks
repeat the tuple shape, decimal/value equality and quote-token requirement
for direct inserts. Existing forced RLS, tenant-login fence, immutable row,
no-truncate and source-basis trigger remain in force. Idempotency binds the
typed payload to the same reviewed fact receipt.

Only ADR-211's page-local report exposes a closed `measurement` object on each
visible fact (`null` for old/untyped rows), labelled
`reviewed_source_stated_not_balance`. Existing fact page, dossier and selected
Markdown exchange shapes stay unchanged; they must not silently acquire a
new lossy amount field. The external read client validates the exact decimal,
unit/currency shape, source-stated label and agreement with the compact value.
The report still returns `numeric_aggregation=none_units_currency_ownership_unverified`.

## Acceptance and next gates

Prove literal quote binding, rejected floats/exponents/unknown units/currency
shape, SQL direct-insert refusal, old-row NULL preservation, source-grant and
stale-evidence filtering, API/client typed round trip, idempotency and populated
upgrade/restore on fictional PostgreSQL. Future tranches need a controlled
predicate registry, robust source-text number parsing, ownership and
multiple-currency policy, duplicate/reconciliation handling, conflict review
and a known-answer company corpus before any amount total is displayed.
Rollback removes the opt-in code path and route field while retaining any
already reviewed typed rows; dropping columns would lose reviewed metadata
and is not an automatic rollback. FOS-Master remains unchanged.
