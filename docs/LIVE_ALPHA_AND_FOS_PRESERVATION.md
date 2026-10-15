# Live alpha path and FOS intelligence preservation

Status: plan and donor audit, not authorization to read personal data or to retire
FOS-Master. The code checkpoint is the synthetic `v0.2.0a2` alpha. FOS-Master is
pinned at `218d5caec2f20b9047fd3eb8e027dc671acf0c15` and stays operational.
The owner chose synthetic-only Fastmail testing on 2026-10-14; the live pilot
sequence below is a future acceptance plan, not current permission to use a real
account or mailbox. A live FileOS root has its own separate approval gate.

## Product boundary

MasterBrain is the eventual owner interface and API. Email is an internal source
capability; FileOS remains a separately operating source while its behavior is
copied, compared and accepted in tranches. One Brain API should answer both the
owner workspace and approved remote assistants. Neither client receives direct
PostgreSQL, Fastmail, filesystem or object-store access.

The first useful live alpha is deliberately read-only: an owner-enrolled, bounded
Fastmail scope; one separately authorized FileOS root in read-only shadow; current
search with citations and coverage; and an evidence-linked company dossier. A
live-mail test does not itself approve FileOS cutover, remote model disclosure or
source writes. In particular, Fastmail's JMAP `mail` scope permits mail management
as well as reading. Our transport allows only read methods, but that is an
application boundary, not a provider-enforced read-only token. Keep that token in
a private connector process and never give it to Brain API or an LLM client.
Fastmail documents personal JMAP API tokens and the `mail` scope in its
[developer guide](https://www.fastmail.com/dev/).
Version-1 `sync-read` can bound iterations and bytes, but its inventory is
account-wide; an iteration limit is not folder/date enrollment. ADR-175/176
add a typed JMAP folder/date filter, metadata recheck and repeated filtered
inventories without the account-wide change feed. ADR-177 pins the account,
lease and cursor in SQL. ADR-178 adds version-2 private operator configuration
for that exact pin, with fictional HTTPS/disposable-database restart and
revocation proof. ADR-179 adds a local owner-reviewed, administrator-assisted
create/disconnect path without provider contact. The real pilot is **still
not approved**: an authorized disposable live test, retention, credential
handling and operational acceptance remain separate gates. No real folder/date
read has occurred.

## What must survive from FOS-Master

| Donor behavior | Exact pinned source | MasterBrain destination and preservation test |
|---|---|---|
| In-place eight-domain inventory, FTS and provenance | `scan_domains.py`, `fos_tools.py`, `content_search.py`, `file_history` schema | FileOS adapter/DataCore; compare identity, hash, exclusions, errors, current/absent semantics and history before any switch |
| Generic entities, amounts, dates and document facts | `extract_facts.py`, `fact_db.py`, `extract_all_domains.py` | KnowledgeCore *candidate* assertions linked to immutable evidence; never promote a parsed amount to a verified holding automatically |
| Repeating statement holdings/transactions and reconciliation | `statement_extract.py`, `statement_line_items`, `statement_extraction_runs`; `CMD_INTELLIGENCE.md` | Separate typed line-item projection, not scalar `claim.value`; golden cases for every recipe, row grouping, totals, failures and repeat runs |
| Source-tier, text-match and hash-pinned confirmation | `fact_verify.py` | Evidence verification policy with explicit source type, document hash, corroboration and disagreement; keep source-tier rules reviewable |
| Cross-domain intelligence reports | `reporting.py`, `report_data_collector.py` | Known-answer query/report parity, including coverage and entity spread; never sum unrelated money mentions as investments |
| Audited file routing and effects | `routing_engine.py`, `safe_fileops.py`, `file_history` | Separate future effect broker with preview, approval, audit and rollback; no effect in the read-only alpha |

The donor `Q: Intelligence` command says generic facts and statement recipes run
together, because a scalar money fact cannot represent each transaction's date,
symbol, quantity, price and amount as one row. Its recipe factory currently names
Streetbeat, Fidelity, OCR bank, Morgan Stanley, Jefferies, Wells Fargo
Savings/Line of Credit/Brokerage and Charles Schwab Brokerage. The donor command
documents material coverage differences and `reconciliation_mismatch`/`error`
outcomes, including a weak Fidelity extraction path. These are donor claims to
measure, not MasterBrain acceptance. There is no dedicated checked-in statement
or intelligence-report test module in the pinned donor; build a synthetic golden
suite before extracting runtime behavior. Do not copy real statements into Git.
ADR-170 now provides a first isolated, fictional Streetbeat recipe candidate and
golden comparison. It is not a runtime ingestion or investment feature; ADR-174
adds Fidelity goldens, while other recipes and reports still need distinct corpora.
ADR-171 adds private exact-decimal/text-span candidates for that one recipe; it
does not validate a source's bytes-to-text derivation, tenant grant or live holding.
ADR-174 adds a separate fictional Fidelity donor baseline, preserving its
low-confidence two-column missed-row and zero-total fallback behavior exactly.
It is not connected to the typed candidate or proposal ledger; a reconciliation
mismatch is a warning about incomplete coverage, not a verified account total.
ADR-180 adds a third, isolated bank-statement recipe baseline for OCR text,
including wrapped amounts and statement-year rollover. It does not run OCR or
publish bank facts. The remaining recipes and donor intelligence reports still
require comparison before any replacement claim.
ADR-181 now compares Morgan Stanley too. Its cash-bucket detail exclusion and
OCR-date loss are preserved as donor behavior, not product-grade investment
analysis. ADR-187 adds a fifth isolated Jefferies baseline, preserving
category-vs-security detail, negative cash and multi-lot grand totals while
exposing unpriced positions and wrapped-activity omissions. ADR-191 adds a sixth isolated
Wells Fargo *savings* baseline with daily-balance sign resolution and explicit
low-confidence mismatch cases. ADR-198 adds a seventh isolated Wells Fargo
*brokerage* baseline for cash, lots, page-break duplicates and incomplete tails.
ADR-199 adds an eighth isolated Wells Fargo *credit-line* text baseline for
the two donor layouts and debt-negative reconciliation. It does not prove
complete PDF extraction for that statement family. ADR-203 adds a ninth,
old-template Schwab supplied-text baseline; scanned/redesigned eras remain
unsupported. ADR-209 begins donor-report comparison with coverage and timeline
row semantics only. The money, entity and cross-domain reports remain
unported, and none of these baselines is a live investment analysis path.
ADR-172 stores selected current-document candidates in an immutable tenant-fenced
ledger, and ADR-173 permits a human owner to inspect bounded, source-rechecked
unreviewed rows through the API. Neither proves a live holding, supplies a
first-party investment dossier, grants assistant access or approves a fact.

## Investment dossier acceptance example

For “tell me all my investments in X company,” the response should:

1. Resolve X and its aliases under the owner's source grants; show ambiguity
   instead of silently merging companies or investment vehicles.
2. Return matching current files and email, with source date, observation date,
   hash-backed citation and original-evidence drill-down. Say which sources and
   document families were not covered or failed extraction.
3. Separate document *mentions*, extracted statement rows, reviewed claims and
   independently confirmed holdings. Keep contradictory amounts/dates visible.
4. Group repeated statements by account, period and position identity before any
   total; do not add balances from successive months or infer ownership from an
   arbitrary dollar mention. Show reconciliation status and currency.
5. Produce a compact, downloadable snapshot/dossier only from those bounded,
   authorized records, with citations and an explicit “as observed” timestamp.
   A generated narrative is a later, separately evaluated layer.

An initial lexical dossier may satisfy discovery only; it must not be labeled a
complete portfolio, verified balance or tax/financial advice.

## Sequenced pilot

The real Fastmail steps are deferred by the synthetic-only decision. Complete
fictional/disposable tests and donor parity first; resume real-mail planning
only after new explicit owner authorization. FileOS live-shadow approval remains
a separate decision.

1. Finish the owner's fictional Email/FileOS browser walkthrough on the tagged
   alpha and record failures before adding personal sources.
2. Decide one Fastmail account, bounded initial folder/date window, retention and
   deletion/export policy, and local-versus-hosted pilot location. The owner creates
   a private Fastmail API token; never paste it into chat or Git. Review the
   [local audited source workflow](FASTMAIL_SCOPE_ENROLLMENT.md), then run
   `sync-read --check` without provider access
   before one explicitly authorized bounded read. Verify counts, held items,
   resume, pause/revoke and evidence in a private environment.
3. Preserve FOS-Master and its SQLite/index/history in place. With a separately
   authorized root, compare read-only donor and MasterBrain inventory/search in
   shadow. Resolve the six documented policy gaps, cloud placeholders and fault
   behavior before any v2 current-read change.
4. Build synthetic golden fixtures for the donor's generic intelligence and
   statement recipes; import only evidence-linked, reviewable projections.
   Compare donor and MasterBrain results, failure states, idempotency and reports.
5. Run the company-dossier known-answer corpus across fictional Email and files,
   then a bounded owner-approved live cohort. Only after read parity and rollback
   may a separate FileOS cutover decision be considered.

## Database and remote access decision

For a short owner-only pilot, a private local PostgreSQL database and private
encrypted evidence storage minimize initial cloud disclosure, but remote access
and uptime depend on the Mac. The target for Grokbot or another remote client is
one managed, private PostgreSQL database plus private encrypted evidence storage
behind an authenticated MasterBrain API. FOS file roots can remain on the Mac,
read by a narrowly enrolled scanner that publishes bounded evidence; a hosted
database does **not** require moving or rewriting the source files. The API is the
network boundary; do not expose PostgreSQL or file shares directly to assistants.

The existing Azure-home preference is conditional, not an approved purchase or
deployment. Before a managed pilot, choose region, budget ceiling, retention,
identity, key custody and backup/recovery targets; verify tenant-bound database
roles, source grants/revocation, TLS/private ingress, content-safe logs and a
populated restore. A private tunnel can serve a local pilot for a controlled
client, but it does not replace application authentication or make an unattended
Mac a reliable hosted service. See [hosting options](HOSTING_DECISION.md),
[deployment](DEPLOYMENT.md), [security](SECURITY.md) and [release gates](RELEASE_ACCEPTANCE.md).
