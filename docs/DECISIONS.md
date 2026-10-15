# Architecture Decisions

[ADR-231](adr/231_email_pdf_replay_account_transition_fence.md) serializes the
reviewed Email PDF receipt with controlled and direct account-status updates
using a tenant-bound worker function; completed document jobs stay immutable.

[ADR-230](adr/230_restricted_email_pdf_tier_replay_command.md) exposes one
reviewed Email attachment PDF text-layer replay through a private, exact-account,
tenant-bound worker command with no selected MIME read in check mode.

[ADR-229](adr/229_reviewed_email_attachment_pdf_replay_receipt.md) binds one
current reviewed Email PDF attachment to a retained-MIME replay and immutable
digest-only receipt. It is not an operator command or financial attestation.

[ADR-228](adr/228_retained_email_attachment_pdf_derivation.md) adds a
nonpublishing exact retained-MIME/part and isolated Email PDF text-layer proof.
It is not a reviewed receipt, live mail or financial attestation.

[ADR-227](adr/227_restricted_fileos_pdf_tier_replay_command.md) exposes one
reviewed FileOS PDF text-layer replay through an exact, tenant-bound private
command with a no-selected-PDF-read check mode. Synthetic execution does not
authorize a live root, financial claim or FileOS cutover.

[ADR-226](adr/226_reviewed_fileos_pdf_replay_receipt.md) binds the confined
PDF derivation to one current human tier review and an immutable digest-only
receipt. The receipt is not OCR, issuer proof or financial truth.

[ADR-225](adr/225_confined_fileos_pdf_derivation_replay.md) adds a
nonpublishing, exact-byte FileOS PDF text-layer replay through the pinned
restricted processor. Image-only and changed sources fail closed.

[ADR-224](adr/224_restricted_email_tier_replay_command.md) exposes one
reviewed retained-Email text replay through a tenant-bound, exact-account
operator command with no selected MIME read in check mode.

[ADR-223](adr/223_retained_email_text_replay.md) proves one direct-parser
Email text projection from current retained MIME (inline or encrypted) and
stores a point-in-time digest receipt, not sender authenticity.

[ADR-222](adr/222_encrypted_email_bridge_source_size.md) binds bridged
encrypted Email versions to their actual retained MIME byte size.

[ADR-221](adr/221_xlsx_formula_and_cell_deferral.md) defers formula-bearing
or overlong-cell XLSX instead of publishing incomplete-looking text.

[ADR-220](adr/220_pdf_missing_page_deferral.md) defers mixed text/no-text PDFs
instead of treating partial page coverage as complete extraction.

[ADR-219](adr/219_restricted_source_tier_replay_command.md) exposes the
bounded FileOS text replay through one tenant-bound worker command.

[ADR-218](adr/218_source_tier_fileos_text_replay.md) binds confined FileOS
text bytes to one current human source-tier review and digest-only receipt.

[ADR-217](adr/217_current_source_tier_review.md) stores a human source-tier
classification of current evidence without calling it byte attestation.

[ADR-216](adr/216_fos_fact_verifier_parity_and_attestation_boundary.md) pins
donor fact-verifier semantics in isolated fictional parity, not verified
financial claims.

[ADR-215](adr/215_project_fact_catalog_discovery_and_retirement.md) makes the
database's latest predicate revision authoritative, including deprecation,
and exposes a bounded read-only Brain API catalog with strict client checks.

[ADR-214](adr/214_project_fact_predicate_catalog.md) pins a versioned
checked-in predicate vocabulary for new reviewed project facts. Publication
code and SQL guard the name/type/unit shape; legacy rows are not reclassified.
Issue #183's aliases and private vocabulary proposals remain open.

[ADR-213](adr/213_project_fact_measurement_quote_tokens.md) refuses partial
amount and unit/currency matches in source-stated measurement quotes at both
application and SQL boundaries. Existing typed rows are checked during the
additive migration, without a silent rewrite.

[ADR-212](adr/212_exact_project_fact_measurement.md) adds opt-in exact-decimal
unit/currency metadata to newly reviewed project facts. Existing values stay
untyped; the report labels measurements as source-stated and still refuses
numeric totals.

[ADR-211](adr/211_current_project_fact_report.md) exposes a first source-
granted, current-evidence project fact report from reviewed KnowledgeCore rows.
It groups one bounded page with citation IDs and uncertainty flags, never a
numeric investment total.

[ADR-210](adr/210_fos_entity_money_report_baseline.md) compares the remaining
three FOS intelligence-report row shapes on fictional data. Duplicate entity
mentions, distinct-domain spread and DuckDB money rounding are pinned, but
the numeric sum is expressly not an investment balance or runtime API.

[ADR-209](adr/209_fos_report_baseline.md) pins the first isolated, synthetic
FOS intelligence-report comparison: coverage and timeline only, with donor
source hash and no runtime, financial-truth or cutover claim.

[ADR-208](adr/208_synthetic_masterbrain_demo.md) adds a disposable, branded
combined Email/FileOS demo and cited project fixture. It leaves live sources,
hosted identity, automatic interpretation and FOS-Master untouched.

[ADR-207](adr/207_project_artifact_markdown_proposal_boundary.md) specifies
separate private selected artifact-link proposals because their approved
receipt differs from generic Knowledge and project-fact receipts. Its
transaction-bound publisher and separate synthetic-only stage/preview/human-
review queue are implemented on an open PR. Local tests do not imply hosted
acceptance, live import or FileOS cutover.

[ADR-206](adr/206_project_fact_markdown_proposal_boundary.md) adds a
synthetic-only, private project-fact Markdown proposal path with explicit
human batch decisions and a fact-specific publication receipt. It remains on
an open PR pending hosted gates, not a live-source or automatic-import claim.
Artifact links and inferred facts remain separate decisions.

[ADR-205](adr/205_dossier_member_proposal_staging.md) admits selected,
two-citation project-member Markdown rows only into the private proposal
queue. Existing local project/entity bases and exact cited evidence are
rechecked through human review; approval issues a new local member ID and
never grants permissions.

[ADR-204](adr/204_fictional_cross_source_project_dossier_acceptance.md)
extends only the disposable cross-source trial with one coherent, reviewed
fictional project dossier spanning Email and FileOS. It tests existing API,
client and Markdown contracts without importing live sources, running model
inference or changing FOS-Master.

[ADR-203](adr/203_schwab_statement_recipe_parity.md) pins an isolated,
synthetic supplied-text Charles Schwab recipe comparison to the unchanged
FOS-Master donor. It does not prove scanned/redesigned PDF extraction, publish
holdings or authorize a FileOS cutover.

[ADR-202](adr/202_dossier_source_stated_proposal_staging.md) allows an owner
to stage selected source-stated project/event/commitment Markdown rows only as
private ADR-186 proposals. It binds exact input/selection context and rechecks
full quotes on their specifically cited current evidence within the batch
transaction; no automatic review, inferred claim or live source follows.

[ADR-201](adr/201_current_dossier_citation_inspection.md) makes the selected
Markdown dossier's claimed quote previews checkable against each current,
authorized evidence ID by an owner-only API. It remains an inspection, not a
full-quote proof, proposal write, approval or live-source authorization.

[ADR-200](adr/200_masterbrain_dossier_format_intake.md) adopts the existing
ADR-197 Markdown export as the owner-selected Librarian exchange format. Its
first intake slice is a bounded, read-only, untrusted candidate inventory;
the export lacks full publication metadata, so no Knowledge proposal is
staged or approved from it.

This is an ADR index plus historical decision summaries. New detailed decisions
live in [adr/](adr/). Later explicit decisions supersede earlier limitations without
rewriting their history. The current status is in [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).
The documentation refresh changes explanations/navigation, not runtime privileges.

ADR-035 now defines the separate approved PDF source-to-search channel for ready
mail. ADR-029/030 remain bounded MIME recovery; no implicit permission expansion.

## Accepted

[ADR-199](adr/199_wells_fargo_credit_line_recipe_parity.md) pins a synthetic
Wells Fargo credit-line text comparison, preserving both donor layouts and
debt-sign reconciliation without claiming source-PDF extraction or a verified
loan balance.

[ADR-198](adr/198_wells_fargo_brokerage_recipe_parity.md) pins a seventh
synthetic-only donor statement recipe comparison for Wells Fargo brokerage.
It preserves cash, lot and reconciliation behavior without publishing holdings
or changing runtime FileOS.

[ADR-197](adr/197_verified_project_dossier_markdown.md) specifies a
synthetic-only, fail-closed cited Markdown view of one bounded reviewed
project. Each older assertion's full stored quote is verified against its own
currently authorized evidence before rendering; it does not infer truth or
permit a live-source cutover.

[ADR-196](adr/196_citation_safe_project_fact_export.md) adds a bounded,
synthetic-only, export-time quote-rechecked Markdown **fact fragment**. It is
not a complete project dossier or an approval to
render historical unverified assertion text as cited prose.

[ADR-195](adr/195_source_stated_project_facts.md) specifies a distinct,
quoted, source-stated project-fact assertion and a source-scoped dossier
section before any Markdown citation claim. Merged PR #228 implements the
synthetic schema, routes and bounded display; exact-head and independent
merged-main gates passed. Inferred facts and a complete Markdown dossier
remain absent.

[ADR-194](adr/194_project_dossier_artifact_section.md) adds an independently
bounded, currently source-authorized reviewed artifact-link history section to
the exact-project dossier and owner workspace. It does not compute a current
file roster, expose bytes or complete the Markdown Librarian export.

[ADR-193](adr/193_reviewed_project_artifact_links.md) adds human-reviewed links
from an exact project to an exact Email/FileOS evidence occurrence, with a
separately quoted basis and source-scoped, bounded link-history API. It neither
auto-matches files nor creates a complete Markdown dossier or source effect.

[ADR-192](adr/192_project_proposal_alias_quote_gate.md) requires each proposed
project alias quote to match its own currently authorized normalized evidence
at stage, preview and review. Older direct reviewed publication remains a
separate citation-validation gap before Markdown export.

[ADR-191](adr/191_wells_fargo_savings_recipe_parity.md) pins a sixth isolated
donor statement recipe: Wells Fargo savings daily-balance sign resolution,
including low-confidence ambiguous groups. It publishes no financial claim.

[ADR-190](adr/190_synthetic_trial_statement_replay.md) exercises ADR-189's
private FileOS byte replay during the disposable fictional browser trial. It
does not change the owner API, review status or live-source authorization.

[ADR-189](adr/189_private_fileos_statement_replay_receipt.md) adds a private,
source-reacquired FileOS text replay receipt bound to one current statement
proposal. It grants no public verified-investment status, Email/PDF/OCR proof,
live source or donor cutover.

[ADR-188](adr/188_statement_source_text_derivation_contract.md) adds a pure,
synthetic-only exact-byte replay for bounded FileOS text transforms. ADR-189
now binds it privately to one current proposal; neither decision proves
PDF/OCR/Email source derivation or a reviewed investment.

[ADR-187](adr/187_jefferies_recipe_parity_baseline.md) pins the Jefferies donor
category/detail/transaction behavior, including negative cash and multi-lot
subtotals, for fictional nonpublishing comparison only. It does not verify a
holding or connect the recipe to runtime intake.

[ADR-186](adr/186_private_knowledge_proposal_batches.md) stages bounded,
source-stated Knowledge assertions outside reviewed search and requires an
explicit per-row human decision in one atomic transaction. It adds no Markdown
parser, inference route or live-source authority.

[ADR-185](adr/185_excluded_email_evidence_visibility.md) closes the retained
Brain and reviewed KnowledgeCore read paths for already-ingested Email that
later becomes mailbox-excluded. It preserves immutable history and existing
human historical access pending an owner retention decision; synthetic only.

[ADR-184](adr/184_scoped_mailbox_exclusion.md) adds a policy-fingerprinted,
pre-download exact mailbox exclusion to synthetic scoped Email intake. It
hides a formerly current message without claiming provider deletion; immutable
history and the minimal internal reconciliation ID remain. No live access,
retroactive purge, or FileOS filter change follows.

[ADR-183](adr/183_reviewed_project_members.md) adds reviewed, immutable
person/organization-to-project role assertions and a bounded, source-grant-safe
dossier section. Roles never confer access or imply a current roster.

[ADR-182](adr/182_reviewed_project_alias_resolution.md) adds evidence-linked
project aliases and ambiguous, candidate-only lookup without automatic merging.

[ADR-181](adr/181_morgan_stanley_recipe_parity_baseline.md) and
[ADR-180](adr/180_ocr_bank_recipe_parity_baseline.md) pin further fictional,
nonpublishing donor statement recipe baselines; neither is a runtime holding.

[ADR-179](adr/179_reviewed_fastmail_scope_enrollment.md) adds a private
human-owner-managed check/enroll/disconnect command. It creates only a new,
already-pinned Fastmail account, or disconnects the exact one while preserving
its pin and evidence. Fictional verification is not a live-provider approval.

[ADR-178](adr/178_private_scoped_fastmail_read_operator.md) adds closed
version-2 private `sync-read` configuration for one exact SQL-pinned Fastmail
window. It checks the pin before provider I/O and at each guarded request,
then uses ADR-176's scoped worker. Version 1 stays account-wide; reviewed live
enrollment and provider acceptance remain open.

[ADR-177](adr/177_fastmail_account_scope_lease_fence.md) pins an exact
Fastmail mailbox/date fingerprint on an unused account and fences worker leases
and cursors in PostgreSQL. The old account-wide operator refuses a pinned
account at preflight. This is synthetic/disposable proof only; ADR-178 adds
the scoped operator and ADR-179 adds local owner-managed enrollment/disconnect.
Live approval remains separate.

[ADR-176](adr/176_scoped_fastmail_inventory_worker.md) adds a synthetic-only
version-4 scoped inventory worker that never uses account-wide changes and
rechecks metadata before bytes. ADR-177 adds its SQL fence and ADR-178 adds
private operator configuration. Live scoped reads remain unauthorized.

[ADR-175](adr/175_scoped_fastmail_query_boundary.md) adds a synthetic-only,
typed mailbox/date `Email/query` filter and independent metadata check. The
account-wide `sync-read` worker is unchanged; a durable scoped pilot is not
yet authorized.

[ADR-174](adr/174_fidelity_recipe_parity_baseline.md) pins a second, deliberately
low-confidence Fidelity statement recipe against fictional donor goldens. It
does not publish or verify holdings, relax ADR-171/172's Streetbeat-only
boundary, or authorize a FileOS cutover.

[ADR-173](adr/173_owner_statement_proposal_preview.md) adds a human-only,
read-only, source-rechecked and paged preview of ADR-172's unreviewed rows.
It neither approves claims nor opens the rows to assistants.

[ADR-172](adr/172_private_statement_proposal_ledger.md) records one current
normalized Email/FileOS document as an immutable, tenant-scoped, worker-only
statement proposal and exact-decimal rows. It is not reviewed investment data,
an assistant route or a FileOS cutover. ADR-173 separately adds owner inspection.

[ADR-171](adr/171_typed_statement_candidate_boundary.md) adds a bounded,
source-neutral, exact-decimal and text-span-bound *private candidate* for the
first statement recipe. It does not publish rows or assert verified holdings.

[ADR-170](adr/170_statement_recipe_parity_seed.md) pins and compares one pure
FOS-Master statement recipe on fictional inputs only. It does not add a runtime
investment feature, database table, reviewed fact or live-source authority.

[ADR-169](adr/169_code_first_librarian_interop.md) fixes the code-first,
proposal-only and evidence-preserving boundary for future Librarian Markdown
import/export. It changes no schema or runtime behavior. The twelve issue
proposals, corrections and staged gates are in the
[interop review](LIBRARIAN_INTEROP.md).

[ADR-168](adr/168_optional_source_availability.md) labels independently optional
Email and FileOS current-search availability without revealing ungranted sources.
An empty result is not mistaken for an absent or unindexed source, and no provider
connectivity or full coverage is implied.

[ADR-167](adr/167_fileos_unencodable_locator_boundary.md) makes v1 FileOS
snapshot and nonpublishing donor shadow reject unencodable names with an
opaque parent coverage error. The transition candidate refuses the fault;
this is a safety divergence, not donor cutover parity.

[ADR-166](adr/166_synthetic_trial_workspace_handoff.md) lets the fictional
loopback trial explicitly reveal its temporary read-only code for manual entry
into `/brain`. It prints or persists no secret and changes no production grant.

[ADR-165](adr/165_answer_citation_recheck.md) reopens only selected answer
evidence after final scoped search, refusing a changed body, digest, source or
revoked read grant before any quote is returned. It is a bounded read-only
race hardening step, not a durable snapshot or generated-chat acceptance.

[ADR-164](adr/164_owner_reviewed_schedule.md) defines explicit, bounded
reviewed-event and commitment-due windows in the first-party workspace. It
reuses ADR-160/161's scoped reads, validates pages and clears stale requests;
PR #159 merged after exact-head full CI, strict-runtime and restore passed;
this is not a live-truth or action surface.

[ADR-163](adr/163_owner_project_dossier_drilldown.md) defines an explicit,
read-only project-dossier drill-down in the first-party workspace. It reuses
ADR-162's scoped route and grants, validates the complete bounded response,
and does not infer live project state or add an action surface. PR #156 merged
after exact-head full CI, strict-runtime and restore passed. Merged-main
restore passed, but full CI and the final strict gate were blocked before
execution by hosted-runner acquisition
([#158](https://github.com/jbone3311/MasterBrain/issues/158)).

[ADR-162](adr/162_reviewed_project_dossier.md) defines a bounded, source-aware
reviewed project dossier with separately limited linked events and commitments,
including undated records. Its state is an assertion, not a current-state reducer.

[ADR-161](adr/161_reviewed_commitments_due.md) defines a bounded,
recorded-cutoff-paged due view for reviewed commitments. It checks direct and
linked-object source grants before limit; this is not current truth, source
freshness, hosted acceptance or an action surface.

[ADR-160](adr/160_reviewed_event_timeline.md) defines a bounded,
recorded-cutoff-paged reviewed-event occurrence timeline with source-aware project
filtering. Undated events remain in exact/history reads; this is not source
freshness or real-world temporal truth.

[ADR-159](adr/159_current_brain_reviewed_leaves.md) selects source-grant-aware
unsuperseded review-chain leaves for grouped Brain current-search and Ask.
Direct KnowledgeCore and grouped unified retained reads remain unchanged;
multiple leaves and partial coverage are explicit.

[ADR-158](adr/158_unsuperseded_reviewed_knowledge_search.md) defines an
explicit, source-grant-aware unsuperseded KnowledgeCore read mode alongside
retained history. It does not select truth, resolve branches or switch the
grouped Brain current-search layer yet.

[ADR-157](adr/157_ask_output_text_budget.md) caps the aggregate UTF-8 bytes
of extractive Ask's exact quotes and separately reviewed match text. It exposes
output truncation without cutting exact citations or claiming a full response
or model-token budget.

[ADR-156](adr/156_shadow_symlink_target_boundary.md) removes symlink-target
type inspection from the nonpublishing FileOS donor shadow. A directory link
becomes a coverage error, and versioned v2 shadow/candidate packets require a
fresh scan and review; v1/current FileOS and FOS-Master are unchanged.

[ADR-155](adr/155_separate_cluster_tenant_restore.md) rehearses a two-tenant
restore into a fresh, separately labelled PostgreSQL 17 container. It retires
stale restored role-name bindings and enrolls new target logins before the
bound-login isolation checks; hosted credential operations remain open.

[ADR-154](adr/154_two_tenant_bound_restore_proof.md) adds an actual
two-tenant bound-login isolation proof before and after the disposable
PostgreSQL restore. It does not accept hosted credential lifecycle or close
issue #7.

[ADR-153](adr/153_required_main_checks.md) requires stable full CI, restore
and runtime-matrix checks before merging to `main`, including administrators.
It changes repository governance, not live-source or FileOS authority.

[ADR-152](adr/152_confined_fileos_shadow_directory_walk.md) confines every
directory of the nonpublishing donor-policy shadow to no-follow descriptors.
A descendant symlink swap cannot enumerate outside filenames; this grants no
publishable policy, v2 activation or FileOS cutover.

[ADR-151](adr/151_ask_utf8_context_budget.md) caps extractive Ask's
selector-visible passage text at 2,048 UTF-8 bytes per passage and 8,192
bytes in aggregate, with explicit truncation coverage. It grants no remote
inference, token budget or source effect.

[ADR-150](adr/150_explicit_brain_source_focus.md) adds an explicit,
read-only Email or FileOS focus to current grouped search and Ask. It avoids
fetching excluded layers and labels their absence as unsearched; it changes
no grant, source effect, v2 visibility or donor cutover.

[ADR-149](adr/149_assistant_legacy_email_denial.md) keeps legacy Email
compatibility API routes outside assistant access. Bootstrap issuance,
OIDC transaction rechecks and route dependencies fail closed for `email.*`
assistant scopes; enrolled assistants use source-filtered Brain reads instead.
Hosted and cache-revocation acceptance remain issue #88.

[ADR-148](adr/148_populated_legacy_rewrite_guard.md) makes the administrator
migrator refuse unapplied 0008/0009 generated-column rewrites on populated
tables unless an operator explicitly opts into the lock-heavy path. This does
not solve issue #9's online-upgrade, later-index or production lock budget.

[ADR-147](adr/147_human_fileos_v2_review_api.md) exposes the existing
historical FileOS v2 search comparison through one human-only, bounded Brain
API route. It keeps current v1 search and SQL-refused v2 activation unchanged.

[ADR-146](adr/146_reviewed_knowledge_in_ask.md) lists bounded, source-scoped
reviewed KnowledgeCore matches beside exact source quotes in Ask. It rechecks
every selected assertion and all of its direct evidence links; reviewed
interpretations are not promoted to source quotations or generated answers.

[ADR-145](adr/145_question_terms_for_extractive_answers.md) removes a fixed
set of question boilerplate before the read-only extractive answer search.
Both initial and final current-source checks use the same lexical terms; the
original question and literal Search only route remain unchanged.

[ADR-144](adr/144_local_extractive_answer_selector.md) supplies a local,
deterministic quote selector for the default Ask path. It makes no semantic
claim or remote model call; explicitly passing no selector restores the
ADR-134 unavailable/fallback behavior.

[ADR-143](adr/143_source_scoped_knowledge_reads.md) admits enrolled assistants
to direct Knowledge search, evidence-linked assertion expansion, filtered
change feeds and unified Brain search. Forward migration 0051 extends OIDC
scope/source fences; hosted and legacy Email acceptance remain issue #88.

[ADR-142](adr/142_source_scoped_brain_read_routes.md) extends enrolled
assistant reads to the remaining directly source-checkable Brain search and
FileOS status routes. SQL filters retained search before limits; exact-source
reads hide ungranted sources. Knowledge/legacy routes and hosted acceptance
remain open under issue #88.

[ADR-141](adr/141_tenant_bound_legacy_email_workers.md) extends opt-in
tenant-bound database access to the three legacy `email-brain` worker commands.
It leaves credential lifecycle and hosted acceptance open under issue #7.

[ADR-140](adr/140_noneditable_synthetic_trial_launcher.md) makes only the
fictional Mac trial launcher use a locked non-editable package install. It
does not change the ordinary developer install or source authority.

[ADR-139](adr/139_tenant_bound_private_derivative_operators.md) extends the
opt-in tenant-login fence to every private `masterbrain` Email bridge and
FileOS archive derivative command, including previews and batches. It leaves
legacy workers, credential lifecycle and hosted acceptance open under issue #7.

[ADR-138](adr/138_tenant_bound_fileos_index_operator.md) adds an opt-in
single-tenant database-login check to private FileOS index build and rollback.
It does not route other workers, retire shared local DSNs or close issue #7.

[ADR-137](adr/137_local_disposable_postgres_trial.md) adds a synthetic-only,
per-run local PostgreSQL 17 alternative to the Docker browser-trial database.
It never targets an existing cluster or live source.

[ADR-136](adr/136_plain_text_search_excerpts.md) removes generated highlight
markers from read-only search excerpts and binds the fictional trial's readable
evidence panel to the selected ID. No ranking, authority or source effect changes.

[ADR-135](adr/135_tenant_bound_fileos_publisher.md) adds an opt-in
single-tenant database-login check to the private FileOS publisher. It
does not route other workers, retire shared local DSNs or close issue #7.

[ADR-134](adr/134_grounded_extractive_answers.md) adds an optional, read-only
extractive answer contract over currently authorized evidence. The selector has
no effects; the server verifies exact quotes and citations. No model adapter is
enabled by default, and this does not certify hosted or named-assistant use.

[ADR-133](adr/133_source_scoped_brain_status.md) extends enrolled assistant
reads to source-filtered current coverage and change status. Hidden-source
cursors fail closed; ADR-142 later extends further Brain reads.

[ADR-132](adr/132_oidc_brain_source_grants.md) adds administrator-owned,
revocable source enrollment to verified OIDC Brain read identities on the
three source-aware routes. It is synthetic/disposable, not hosted or
named-assistant acceptance.

[ADR-131](adr/131_fileos_v2_readiness_set_check.md) changes only the exact
FileOS v2 readiness chunk-closure and base-count queries to indexed per-row
checks under the same statement budget. It grants no v2 activation, current
visibility or cutover.

[ADR-130](adr/130_assistant_source_scoped_reads.md) introduces explicit,
synthetic-bootstrap source enrollment for the three assistant Brain read routes.
It does not provide hosted or dynamically revocable source grants.

[ADR-129](adr/129_read_only_external_brain_client.md) defines a provider-neutral,
read-only HTTP reference client over the same current-search and separately
scoped evidence routes as `/brain`. It is not a hosted or named-assistant adapter.

[ADR-128](adr/128_private_fileos_v2_search_preview.md) permits a scoped,
human-only comparison of one ready historical FileOS v2 generation with the
active v1 generation. It does not add a public route, activate v2 or attest
live-root freshness.

[ADR-127](adr/127_first_party_read_workspace.md) defines a first-party,
read-only conversation-shaped search workspace over the existing scoped Brain
API. It adds no model synthesis, source effects, stored history or privilege.

[ADR-126](adr/126_fileos_v2_shared_index_generation.md) extends the common
DataCore generation contract to an exact v2 completion/document attempt while
keeping v2 activation forbidden in SQL. It defines a private builder and
readiness gate, not current visibility, absence or donor cutover.

[ADR-125](adr/125_fileos_v2_baseline_document_publication.md) accounts for
bounded normalized documents on the exact prepared v2 baseline. A complete
attempt can be ready or blocked, but neither outcome activates current reads,
infers absence or cuts over FOS-Master.

[ADR-124](adr/124_fileos_v2_baseline_completion.md) seals one historically
complete, owner-authorized FileOS v2 baseline after a fresh exact donor-policy
scan. Its private receipt reuses the immutable staged membership ledger;
current reads, absence and FOS-Master cutover remain unchanged.

[ADR-123](adr/123_fileos_v2_baseline_authorization.md) requires a distinct,
human-owner authorization bound to the exact reviewed plan and prepared v2
evidence. It is synthetic-only and does not complete a v2 run, switch reads,
infer absence, or authorize FOS-Master cutover.

[ADR-122](adr/122_fileos_run_ledger_linear_validation.md) makes the existing
FileOS v1 completion ledger check linear in run size while preserving deferred
whole-run validation, late-insert refusal and source serialization. It changes
no v2 publication or FileOS cutover authority.

[ADR-121](adr/121_fileos_v2_prepared_evidence.md) permits a private,
worker-scoped FileOS v2 evidence-preparation transaction after another exact
fresh scan. It maps donor candidate versions to policy-scoped DataCore versions
without changing v1 current state, completion, search, absence or cutover.

[ADR-120](adr/120_sandbox_failure_stage_diagnostics.md) permits fixed-code,
content-safe failure-stage warnings from the trusted isolated-processing
controller. Public failures remain scrubbed and fail closed; the diagnostic
does not claim issue #64's intermittent root cause is solved.

[ADR-119](adr/119_fileos_v2_baseline_verification.md) requires a worker-scoped,
fresh donor-policy scan to match an approved staged inventory exactly before
recording an immutable verification receipt. It does not publish v2 or switch
current FileOS state.

[ADR-118](adr/118_fileos_v2_transition_review_approval.md) binds one human
owner's decision to an exact, current FileOS v2 staged plan and count maps.
The immutable approval receipt is nonpublishing and not cutover authority.

[ADR-117](adr/117_fileos_v2_staged_inventory.md) adds a relational,
nonpublishing FileOS v2 staging ledger. Hashless donor observations persist
without fabricated versions or digests; staging is not freshness or cutover.

[ADR-116](adr/116_private_fileos_transition_review_read.md) allows a compact,
locator-free private summary and separately scoped, bounded detail pages of a
sealed transition packet. Current-run status is not transition approval.

[ADR-115](adr/115_fileos_transition_review_packet.md) retains one donor-policy
candidate and its exact completed-v1 comparison in a private immutable review
packet. It creates no v2 baseline, publication or FileOS cutover authority.

[ADR-114](adr/114_completed_fileos_baseline_preview.md) binds the private
donor-policy preview to the latest exact completed v1 database run, checking
before and after source scanning. It creates no v2 baseline or publication.

[ADR-113](adr/113_fileos_policy_transition_preview.md) permits only a private,
nonpublishing v1-to-donor policy comparison. It never infers deletion or
authorizes v2 publication; baseline persistence and owner acceptance remain open.

[ADR-112](adr/112_fileos_donor_candidate_ledger.md) defines a source-bound,
nonpublishing donor-policy candidate. Hashless donor rows remain deferred without
invented versions or evidence; v1 intake and FileOS completion remain unchanged.

[ADR-111](adr/111_fileos_donor_policy_shadow.md) adds an isolated read-only
FOS scanner-policy shadow profile. It changes no publishable FileOS snapshot,
completion policy, operator, or FOS-Master behavior; donor-policy adoption and
live-source acceptance remain separate decisions.
[ADR-110](adr/110_fastmail_sync_resilience.md) pages Fastmail listings by anchor,
holds oversized mail as accounted `source_too_large` receipts instead of pausing
the account, reuses retained bytes for unchanged blobs and treats a lost lease as
an outcome. It grants no mailbox write, enrollment or live acceptance.

[ADR-109](adr/109_tenant_database_routing.md) adds an opt-in API service path
with an identity-only lookup DSN and one database-fenced login per configured
tenant. Private workers, credential lifecycle and hosted acceptance remain open.

[ADR-108](adr/108_tenant_login_rls_fence.md) adds an opt-in restrictive RLS
fence for DBA-bound one-tenant PostgreSQL logins. Existing shared logins retain
their risk; issue #7 remains open pending DSN routing and hosted acceptance.

[ADR-107](adr/107_current_archive_image_search.md) adds a distinct current-only
archive-image OCR layer with exact receipt, sealed-member and parent freshness
fences. It grants no OCR execution, automatic selection or FileOS cutover.

[ADR-106](adr/106_identity_resolver_boundary.md) moves runtime identity reads
behind an exact-key definer function and removes direct table SELECT. It reduces
the caller-settable lookup surface but does not close issue #7's arbitrary-SQL
tenant-context threat.

[ADR-105](adr/105_identity_admin_enrollment.md) provides a dedicated
non-superuser identity-administration role under forced RLS and a protected audit
trigger. It addresses issue #6 without granting runtime writes or resolving the
separate caller-settable lookup-context concern in issue #7.

[ADR-104](adr/104_privacy_safe_error_observability.md) adds content-free
request-failure categories and a sanitized 500 response with a server-generated
request ID. It does not claim production log retention, alerting or incident response.

[ADR-102](adr/102_strict_sender_runtime.md) requires a security-patched
strict sender parser at startup and keeps unsupported Python patches from silently
losing rule effects. PR #31 is merged on `main`; this is not sender authentication.

[ADR-101](adr/101_synthetic_alpha_release.md) defines the test-only `0.2.0a1`
checkpoint and the branch/PR/test/merge/tag cadence. It does not authorize live
sources, production deployment, FileOS cutover or FOS-Master retirement.

[ADR-100](adr/100_confined_fileos_reads.md) requires descriptor-relative,
no-follow, bounded FileOS snapshot and extraction reads before bytes are hashed or
parsed. The isolated implementation and adversarial regressions passed hosted CI,
donor shadow and populated restore on PR #25's tested head. Integrated into
`main` via cumulative PR #28; donor policy and FOS-Master remain unchanged.

[ADR-099](adr/099_archive_ledger_and_parent_integrity.md) requires archive child
inserts to keep sealed inventory counts/bytes balanced at commit, binds provenance
outputs to normalized documents and binds text/document/image receipt parent
versions to their exact inventory. Forward-only migration 0033 passed hosted
PostgreSQL CI and populated restore on PR #24's runtime head. Integrated into
`main` via cumulative PR #28.

[ADR-098](adr/098_fileos_root_binding.md) binds FileOS intake and completion to a
versioned physical-root digest. Historical unknown roots are not silently claimed.
Implemented in isolated PR #22; hosted CI and populated restore passed on the
runtime head. Integrated into `main` via PR #28; this is not a donor-policy switch
or cutover.

[ADR-097](adr/097_fileos_exclusion_ledger.md) requires a bounded, exact FileOS
snapshot exclusion ledger and refuses absence inference when a previously indexed
locator is now excluded or intentionally skipped. It leaves donor policy and
FOS-Master unchanged. Implemented; hosted CI and populated restore are green on
PR #21's runtime head. Integrated into `main` via PR #28.

[ADR-096](adr/096_fileos_inventory_policy_identity.md) binds new FileOS completion
receipts to a validated versioned inventory-policy digest and refuses absence
inference across unknown or changed policies. It does not authorize automatic
rebaselining or donor cutover. Implemented; hosted CI and populated restore are green
on PR #20's runtime head. Integrated into `main` via PR #28.

[ADR-095](adr/095_fileos_mass_loss_guard.md) refuses a new FileOS completion when
at least 10 prior items and at least half the prior inventory disappear. It does
not authorize a bypass, policy switch or donor cutover. Implemented; hosted CI
and restore are green on PR #19.

[ADR-094](adr/094_fileos_completion_coverage.md) requires a fail-closed snapshot
error ledger before FileOS completion and absence inference. It permits only an
explicit no-follow symlink skip; policy-version and mass-loss guards remain later
decisions. Implemented; hosted CI and restore are green on PR #18.

[ADR-093](adr/093_fileos_inventory_shadow.md) authorizes only a pinned,
synthetic-database FileOS scanner-vs-snapshot shadow comparator. It requires exact,
reason-coded policy divergences and no source or publication effects; a later ADR
must decide an integrated inventory-policy switch.

[ADR-092](adr/092_protected_record_truncate_guards.md) adds forward-only
statement-level `TRUNCATE` refusal for append-only evidence, protected jobs and
audited identity bindings. It leaves legitimate row-level transitions and runtime
grants unchanged. See the [truncation contract](EVIDENCE_TRUNCATE_GUARDS.md).

[ADR-091](adr/091_migration_integrity.md) requires an explicit privileged
migration-role preflight and a forward-only audit/repair of legacy Email
`message_sync_state` gaps. It preserves applied checksums and current evidence;
runtime roles retain forced RLS. Implementation and hosted gates are green in
[PR #12](https://github.com/jbone3311/MasterBrain/pull/12); the implementation
was integrated via PR #28, and issue #5 closed after direct PostgreSQL regression
coverage. See the [migration integrity contract](MIGRATION_INTEGRITY.md).

[ADR-090](adr/090_private_archive_image_operator.md) defines the private,
authenticated one-member archive-image OCR command using the accepted 5A composition
and 5B publication contracts. Implemented in `f658ace`; hosted CI and populated
restore are green. Current search remains a separate 5D proposal.

[ADR-089](adr/089_archive_member_image_persistence.md) defines append-only publication
for one explicit, nonempty, successful archive-image OCR result with a separate forced-
RLS receipt, exact current-parent/member fence and image-specific provenance.
Implemented through `63b478d`; that checkpoint did not yet authorize a command,
search, batch or fan-out. ADR-090 later authorized one private command.

[ADR-088](adr/088_archive_member_image_ocr.md) composes only one explicit current,
hash-bound archive member with the separate image worker, returns a bounded in-memory
result and grants no persistence, command, batch or fan-out. Implemented in `b17541d`;
real two-image acceptance is
[CI 35829326066](https://github.com/jbone3311/MasterBrain/actions/runs/35829326066).

[ADR-087](adr/087_archive_image_ocr_boundary.md) requires a separate immutable,
non-networked image worker with exact byte/format binding, full decode, single-frame
policy, 25-megapixel/20-second/5,000-character limits and no EXIF, database, command
or external-vision effects. The isolated worker is implemented through `512185b`;
archive composition and publication were deferred at that checkpoint and are covered
by later ADRs.

[ADR-086](adr/086_sealed_archive_document_batch.md) requires a private canonical plan
of explicit locator/expected-format/key triples, sequential execution through both
existing workers, fail-stop refusal and unchanged-plan replay. Implemented in
`87ea0d0`.

[ADR-085](adr/085_private_archive_document_preview.md) requires a private, bounded,
non-consuming view of exact current PDF/Office candidates before any document batch
format or executor is considered. Implemented in `1651c2b`.

[ADR-084](adr/084_current_archive_document_search.md) keeps current archive-contained
PDF/Office derivatives in a distinct, independently ranked layer, fenced through the
document receipt and exact current parent/member identity. Implemented in `7329ba9`.

[ADR-083](adr/083_archive_member_documents.md) composes the existing hash-bound member
reader with the existing isolated PDF/Office worker for one explicit selection, using
a separate receipt and no raw-byte persistence. Implemented through `5bb1aa1`; real
two-image acceptance is `49b8383`.

[ADR-082](adr/082_sealed_archive_member_batch.md) requires one canonical private plan
with caller-supplied keys and fail-stop exact-plan retry before archive-member batch
publication is authorized. Implemented in `1a3fd58`.

[ADR-081](adr/081_private_archive_member_preview.md) requires a private, read-only,
ordinal-cursor preview of eligible members in one current archive inventory before any
sealed batch format or executor is considered. Implemented in `0a8c430` with fixture
correction `5befc42`.

[ADR-080](adr/080_current_archive_derivative_search.md) keeps explicitly published,
still-current archive-member text in a separate bounded search layer. Currency is
proved through the parent archive and sealed inventory/member identities; active
FileOS generations remain immutable. Implemented in `6c7b043`.

[ADR-079](adr/079_private_archive_member_text_operator.md) requires a private,
reauthenticated, content-free one-member command before archive text publication.
Implemented in `257ab30`, with hardened acceptance in `d66de6e`.

[ADR-078](adr/078_archive_member_text_derivative.md) gives one explicitly selected
archive member its own derived evidence identity before bounded text publication.
Implemented in `97aeab1`.

[ADR-077](adr/077_hash_bound_archive_member_read.md) defines a separate isolated
command that returns at most one persisted non-container member by exact source and
member hash/size, capped at 8 MiB and still unscanned. Implemented in `c7d2d27`.

[ADR-076](adr/076_archive_manifest_persistence.md) defines an append-only forced-RLS
hash-manifest ledger for accepted archive inventories. It creates no child evidence,
member reads or search visibility. Implemented in `03dbb98` with correction `08ccb68`.

[ADR-075](adr/075_fileos_archive_inventory_worker.md) defines an isolated in-memory
ZIP/TAR inventory worker before any member-byte or search publication. It preserves
the pinned donor's bounded recognition/accounting contract while explicitly refusing
duplicate-name ambiguity and bomb publication. Implemented in `26473de`.

[ADR-074](adr/074_sealed_email_part_bridge_batch.md) defines a digest-bound,
single-kind attachment or approved-document plan with fixed per-item keys, fail-stop
execution and exact-plan replay. It authorizes no dependency discovery, mixed-kind
execution or best-effort continuation; hosted PostgreSQL and restore verification are
green.

[ADR-073](adr/073_email_part_bridge_preview.md) defines separate bounded, private and
non-consuming previews for current bridged-message attachments and already-approved
document derivatives. It preserves dependency order and exposes no content or batch
execution authority; hosted PostgreSQL and restore verification are green.

[ADR-072](adr/072_sealed_email_bridge_batch.md) defines a digest-bound, explicit
1–100 item Email bridge plan with fixed per-item idempotency keys, fail-stop execution
and exact-plan retry. It authorizes no discovery, implicit pagination or best-effort
continuation; hosted PostgreSQL and restore verification are green.

[ADR-071](adr/071_email_bridge_backfill_preview.md) defines a private, bounded and
non-consuming current-Email bridge plan for one explicit account. It establishes safe
selection and paging without adding batch writes, provider access or a Brain API
mailbox-enumeration surface; hosted PostgreSQL and restore verification are green.

[ADR-070](adr/070_current_source_coverage.md) defines a bounded, separately authorized
status view for active FileOS generation readiness and explicitly bridged current Email
coverage. It exposes only registered opaque sources and existing facts; hosted
PostgreSQL and restore verification are green.

[ADR-069](adr/069_grouped_current_source_search.md) defines a compact grouped read
across active FileOS, current Email-family evidence and reviewed KnowledgeCore with
independent limits/ranks and explicit partial coverage. Hosted PostgreSQL and restore
verification are green.

[ADR-068](adr/068_current_email_family_search.md) defines a separate, layered current-
only read for bridged Email messages, attachment text and approved PDF derivatives.
Existing message-only and retained-history reads remain unchanged; hosted PostgreSQL
and restore verification are green.

[ADR-067](adr/067_email_part_bridge_operator.md) defines explicit private commands
for one Email attachment occurrence or one approved PDF derivative, reusing the exact
shared worker scopes and non-consuming preflight. Hosted PostgreSQL and restore
verification are green.

[ADR-066](adr/066_email_document_extraction_bridge.md) defines a separate additive
bridge for an immutable approved Email PDF extraction onto its existing shared
attachment evidence. It reuses bounded legacy text and never reads attachment bytes;
hosted PostgreSQL and restore verification are green.

[ADR-065](adr/065_email_attachment_bridge.md) defines an additive bridge preserving
each Email attachment occurrence as a shared child evidence/part. Existing bounded
text may be indexed; unsafe bytes and approved document revisions are not reprocessed
or rewritten. Hosted PostgreSQL and restore verification are green.

[ADR-064](adr/064_current_bridged_email_search.md) defines an additive Brain read for
explicitly bridged Email evidence that is still current and visible in both shared and
legacy state. Existing Email and retained searches remain unchanged. Hosted
PostgreSQL and restore verification are green.

[ADR-063](adr/063_email_bridge_operator.md) defines a private one-version Email bridge
command with exact shared worker scopes, non-consuming preflight and content-free
output. It adds no scan, scheduler, provider access or search cutover. Hosted
PostgreSQL and restore verification are green.

[ADR-062](adr/062_email_evidence_bridge.md) defines an additive, replayable bridge
from one current immutable Email version into shared DataCore identities, chunks and
provenance. Existing Email ingestion/search remain authoritative; no mailbox access,
automatic backfill or cutover is granted. Hosted PostgreSQL and restore are green.

[ADR-046](adr/046_structured_memory.md) adds reviewed trip/flight/hotel/bill memory,
immutable revisions, independent change cursors and explicit partial freshness.
Migration 0014 and bounded REST/developer UI do not imply automatic interpretation.

[ADR-045](adr/045_owner_message_reader.md) adds a human-only full small-message
reader, explicit original/leaf-part exports and source/authority verification.
Large messages retain explicit projection limits and intact original downloads;
MCP/assistant evidence remains bounded. No mailbox privileges or migration.

[ADR-044](adr/044_review_fixes.md) fixes signing-key cache contention and lost
sender ambiguity. Single-flight refresh preserves valid cached access; source-bound
sender-rule eligibility fails closed for historical evidence without validation.

[ADR-043](adr/043_browser_operator_tls.md) adds explicit private browser-mode TLS
startup, mutually exclusive authentication flags and non-consuming preflight.
It preserves loopback-only binding; UI and actual browser acceptance remain gates.

[ADR-042](adr/042_browser_authorization_sessions.md) defines the explicit browser
code/PKCE and server-side session flow. The optional backend/REST boundary exists;
ADR-043 supplies the operator command; owner UI and actual browser/TLS acceptance remain required.

[ADR-041](adr/041_stream_deadline_checks.md) closes application chunk-buffering
gaps in the four HTTP readers, with bounded accumulation and delayed-EOF checks.
Existing scopes, response limits and connector availability remain unchanged.

[ADR-040](adr/040_access_token_identity.md) adds the configured access-token
resource-server boundary, explicit RFC/Entra profiles and administrator-owned
identity bindings with current SQL authorization and administrator audit. Exact
verification is in the build receipt; browser login, real issuer enrollment and hosted release remain gates.

[ADR-039](adr/039_read_worker_controller.md) adds explicit bounded Fastmail read
operation, non-consuming private preflight, exact ingest-worker identity and fresh
file/account guards. No enrollment, schema/grant change or live acceptance.

[ADR-038](adr/038_document_owner_review.md) adds separate owner PDF approval/history/
cancellation and bounded cited page evidence, plus opt-in document search. It uses
existing APIs and source/authorization fences; no schema or permission expansion.

[ADR-037](adr/037_documentation_verification.md) strengthens offline documentation
inventory/path/section-link checks, including GitHub templates, with regression tests.
It adds a methods reading guide but no runtime or permission change. The next
runtime assignment at that increment was the document owner interface, now ADR-038.

[ADR-036](adr/036_document_operator_controller.md) adds the separate explicit PDF
operator command, fixed-purpose/policy private configuration, exact document-worker
identity and loopback server channel option. Shared controller primitives preserve
MIME permissions. Demo owner credentials now use an explicit human-scope allowlist.
No new schema, dependency, live policy or owner-screen controls.

[ADR-035](adr/035_approved_document_processing.md) adds synthetic-only document
approval/jobs, immutable extraction revisions, opt-in FTS and cited results.
Migration 0012 and a separate worker scope preserve source/body state. ADR-036 adds
operator execution and ADR-038 adds owner UI; live/scanner and hosted acceptance remain.

[ADR-034](adr/034_source_bound_pdf_worker.md) adds an explicit source-bound restricted
PDF worker, separate image/contract and synthetic tests. No attachment queue,
publication, scanner, API or broader MIME recovery authority is granted. The next
durable approval-to-search design remains open.

[ADR-033](adr/033_known_answer_synthetic_mailbox.md) adds coherent fictional MIME,
independent format checks, known-answer manifests and bounded/paced synthetic
ingestion through existing transactions. No live delivery or binary extraction.

[ADR-032](adr/032_operator_processing_controller.md) adds an explicit private,
bounded operator command for approved jobs, configuration preflight and graceful
shutdown. It adds no enrollment, SQL grants, schema or hosted service.

[ADR-031](adr/031_processing_review_screen.md) adds bounded durable processing
history and explicit owner-screen approval/cancellation, with session/view fencing
and uncertain-request idempotency. No worker or mailbox capability is enabled.

[ADR-030](adr/030_durable_recovery_jobs.md) connects explicit human approval to
durable isolated-processing jobs, bounded claims/retries and atomic fenced
completion. API and worker remain separate; no hosted identity or daemon is enabled.

[ADR-029](adr/029_isolated_large_mime_recovery.md) adds a restricted, image-bound
large-MIME processor for the human-authorized Recovery library. Default API parsing
and binary-extraction deferral remain unchanged. Docker control is a separate
trusted worker privilege, never granted to the API or untrusted parser.

[ADR-028](adr/028_encrypted_large_evidence.md) adds opt-in encrypted filesystem raw
evidence and SQL manifests (0009), large-message holding and coordinated synthetic
object/database restore. It supersedes historical small-message-only preservation
statements, not parser limits. No hosted storage or binary extraction is implied.

[ADR-027](adr/027_quarantine_recovery.md) adds audited, human-requested retry of
current held MIME and parser-versioned evidence (migration 0008). It supersedes
the no-retry UI boundary in ADR-021; no raw-download or mailbox permission is added.

### ADR-001 — Hosted PostgreSQL is authoritative

**Decision:** managed PostgreSQL + `pgvector`; encrypted object storage for raw blobs.  
**Why:** multi-user concurrency, transactions, RLS, PITR, full-text and vector retrieval in one system.  
**Consequence:** higher operations/cost than local SQLite; requires strict runtime roles and restore testing.

### ADR-002 — SQLite is optional edge/cache only

**Decision:** use encrypted SQLite FTS5/optional vector extension for offline tenant-scoped replicas, never shared authority.  
**Why:** local speed/privacy without multi-writer/synchronization ambiguity.

### ADR-003 — Modular monolith first

**Decision:** one codebase with clear modules; separate deployment boundaries only for ingress, untrusted inference, and mailbox executor where privileges differ.  
**Why:** simpler delivery with enforceable security boundaries.

### ADR-004 — Provider-native incremental sync

**Decision:** Fastmail JMAP, Gmail History/Pub/Sub hint, Graph delta/change-notification hint, iCloud IMAP UID/UIDVALIDITY/IDLE hint.  
**Why:** less polling and correct change semantics. Notifications are hints; cursors/reconciliation are truth.

### ADR-005 — Evidence/events immutable; projections rebuildable

**Decision:** preserve raw versions/hashes, event/action audit, and evidence links.  
**Why:** replay, correction, provenance, rollback, and debugging.

### ADR-006 — Code → local → remote → human ladder

**Decision:** deterministic rules first, local constrained model second, remote escalation only by policy, human review by consequence.  
**Why:** privacy, cost, latency, and reliability.

### ADR-007 — Control-plane proposals, not self-modification

**Decision:** assistants propose typed changes; safe config/knowledge follows review policy; software changes go to Factory.  
**Why:** prevent silent behavioral drift and preserve governance.

### ADR-008 — Draft-only and staged deletion initially

**Decision:** no auto-send or permanent auto-delete in v1; use `_GrokBot/Review Delete` and provider drafts.  
**Why:** irreversible consequences exceed early classifier confidence.

### ADR-009 — Hybrid retrieval without vector dependence

**Decision:** exact/structured + PostgreSQL FTS first; vectors/reranking added by measured benefit.  
**Why:** email identifiers and numbers favor lexical retrieval; degraded mode remains useful.

### ADR-010 — Relational temporal facts before graph database

**Decision:** entities/relations/facts with bitemporal fields in PostgreSQL. Use Graphiti as a pattern/reference and possible later pilot.  
**Why:** reduce infrastructure and keep authorization/transactions unified.

### ADR-011 — REST authority, MCP adapter

**Decision:** stable REST/JSON service contract; MCP exposes narrow typed tools/resources over it.  
**Why:** clients remain replaceable and MCP security/evolution are isolated.

### ADR-012 — Isolation in API and RLS

**Decision:** API authorization plus forced RLS and tenant-aware object/cache keys.  
**Why:** defense in depth. PostgreSQL documents RLS behavior and bypass cases ([docs](https://www.postgresql.org/docs/17/ddl-rowsecurity.html)).

## Accepted prototype evolution

### ADR-013 — Executable foundation and bounded bootstrap (2026-09-19)

**Decision:** ship a loopback-only developer service with synthetic ingestion,
PostgreSQL FTS/evidence, atomic cursor checkpoints, idempotent reviewed proposals,
and a read-only Fastmail protocol adapter. Do not connect real accounts, provision
paid hosting, execute mailbox writes, or enable remote inference during bootstrap.
The user authorized private repository creation, publication, and implementation.

**Auth boundary:** bootstrap credentials are random bearer tokens mapped by their
SHA-256 digests to server-configured tenant/actor/scopes, with an expiry. Only
existing owner memberships are supported; invited members and resource sharing
remain disabled until grant-aware authorization and OIDC are implemented. This
is not production authentication. Tenant/actor never come from request bodies.
Runtime DB credentials must be non-owner, non-superuser, and non-BYPASSRLS.

**Evidence boundary:** bounded raw MIME is retained in a tenant-isolated PostgreSQL
table for this synthetic prototype, atomically with its projection and checkpoint.
Encrypted object storage is still the production target. No public raw-byte API.
Raw objects are immutable while retained, not exempt from authorized retention/purge.

**Review boundary:** proposals are immutable requests. A human owner can mark them
approved/rejected with optimistic version checks; approval does not apply a rule
or execute an action. Feature requests stay data until Factory explicitly adopts
them. This avoids mistaking a review queue for a completed action executor.

**Factory boundary:** a sibling Dropbox source checkout is the desired final local
layout; live databases, venvs, secrets, indexes, and worker state must live outside
Dropbox. Prepare registration artifacts but do not modify Factory itself or claim
its bind/audit passed. Email Brain runtime never imports Factory.

**Verification:** pure unit/API tests plus a real PostgreSQL CI service test RLS,
composite tenant/account foreign keys, replay, transaction rollback, stale cursors,
idempotency conflicts, proposal transitions, and least-privileged runtime roles.

**Rollback:** API is additive; stop it and restore the database from backup if
required. Do not down-migrate/delete retained evidence. No mailbox compensation
is needed because no provider write path exists.

Sources: [Psycopg transactions](https://www.psycopg.org/psycopg3/docs/basic/transactions.html),
[PostgreSQL RLS and bypass behavior](https://www.postgresql.org/docs/17/ddl-rowsecurity.html),
[FastAPI test client](https://fastapi.tiangolo.com/tutorial/testing/).

## Historical attachment boundary (superseded in part by later ADRs)

### ADR-014 — Factory-shaped attachment receipts, bounded extraction (2026-09-19)

**Decision:** extend the transactional ingestion slice with per-MIME-part attachment
receipts and append-only intake events; keep every occurrence, link duplicates
within an account, and retain original bytes in the raw MIME evidence. Extract
bounded plain-text attachments without models. PDFs, Office files, images, archives,
executables, and nested emails receive explicit deferred/skipped status. They are
not executed, unpacked, OCRed, or marked safe by the API process. No raw download
or outbound SMTP capability is introduced.

**Rationale:** Factory's intake standards require receipt accounting, provenance,
per-document outcomes, and no filename-only embeddings. Its document/archive
tools are valuable but currently path/config/CLI-oriented, with optional imports
and some logging that can contain private paths. A long-running multi-tenant
service needs an isolated, deterministic worker contract first. Do not make the
hosted service import a sibling Factory checkout or copy its governance runtime.
See [Factory intake review](FACTORY_INTAKE_REVIEW.md).

**Limit:** complete MIME is currently capped at 1 MiB; attachments at 256 KiB for
plain-text extraction, 64 recorded attachment parts per message, MIME depth 20.
These are prototype limits, not final product limits. Oversized/over-complex MIME
aborts the page without advancing its cursor. Durable poison-message quarantine
and larger encrypted object storage must precede real mailbox backfill.

**Retention:** preserving evidence does not grant infinite retention. A separately
authorized purge workflow must remove message bodies, attachment projections,
objects, vectors, and cache copies; no such destructive workflow runs in v0.1.

**Tests:** path traversal filenames, executable signatures under misleading names,
binary disguised as text, duplicate receipts, archive/nested handling, MIME limits,
attachment FTS, RLS, immutable receipt-event history, and reconciliation counts.

## Accepted provider and worker evolution

### ADR-015 — Fastmail read-only HTTP transport (2026-09-19)

**Decision:** implement and mock-test a Fastmail-specific HTTPS transport with a
fixed `api.fastmail.com` host boundary, no redirects/environment proxy inheritance,
timeouts, bounded streamed responses, and JMAP read-method allowlist. Session
discovery, metadata fetch and raw-blob reads are available as a library. Tokens are
supplied by the caller; no token is discovered or stored by the adapter.

**Boundary:** no live account is contacted during the build; no write/submission
methods or SMTP exist. This is not yet a backfill scheduler or credential enrollment
flow. State/checkpoint policy remains in the ingestion worker design, not HTTP code.
Provider errors are typed and scrubbed, with explicit throttling/auth/expired-state
outcomes. Disposable-account authorization is still required for live acceptance.

Sources: [Fastmail JMAP](https://www.fastmail.com/dev/),
[JMAP blob download](https://jmap.io/spec-core.html#downloading-binary-data).

## Worker history and pending deployment choices

### ADR-016 — Resumable read worker with fenced leases (2026-09-20)

**Decision:** add a bounded, one-page-at-a-time Fastmail worker. Persist a versioned
checkpoint containing the import generation, baseline Email state, query state,
position and total. Restart listing when query state changes; do not infer deletion
from an incomplete listing. Replay changes from the baseline after listing finishes.
Keep the original Email baseline when restarting a changed query. An expired change
cursor pauses with `resync_required`: a complete inventory-diff reconciler is still
needed before safely replacing the baseline. Explicit provider tombstones hide
current search while retained evidence remains available.

**Concurrency:** acquire a database-clock lease before network work, renew between
bounded requests, and fence commits with the exact lease token. Network requests
never run inside a database transaction. Checkpoint and evidence commit together;
an expired/replaced lease cannot commit. A configured provider-account binding is
required and checked against session discovery before reading messages.

**Failure:** persist bounded, content-free run outcomes, retry deadlines and auth/
protocol pauses. No sleeping retry loop in the worker. MIME failures and oversized
messages still stop the page without advancing: durable byte-preserving quarantine
and larger object storage are separate gates, not simulated as successful imports.
Partial full imports are searchable but never advertised as a complete mailbox.

**Boundary:** library orchestration and synthetic/provider-mock tests only initially;
no automatic discovery of credentials, enrollment, real mailbox contact or mailbox
writes. Operator enrollment, scheduler and disposable-account acceptance remain gates.
No inference or binary extraction is enabled by synchronization.

**Rollback:** stop workers; leases expire. Preserve new tables/checkpoints and deploy
forward-compatible code. Older code must not interpret the worker's JSON checkpoints
as provider state. No destructive down migration or provider compensation is required.

Sources: [JMAP query-state contract](https://www.rfc-editor.org/rfc/rfc8620#section-5.5),
[JMAP mail changes](https://www.rfc-editor.org/rfc/rfc8621#section-4.2).

- Cloud/managed Postgres vendor and region.
- OIDC/Zero Trust vendor.
- First provider and exact backfill window.
- Tenant sharing granularity and household/team UX.
- Raw body/attachment retention and compliance obligations.
- Local model/embedding/reranker selected by benchmark.
- Talon vs alternative quote/signature parser after corpus test.
- Whether an edge replica is worth device/key/revocation complexity.
- Search index partitioning and HNSW threshold.
- Remote-model providers and data-retention contractual mode.
- UI framework; architecture does not require one.

### ADR-017 — Certified inventory reconciliation and durable MIME quarantine

Supersedes the earlier bounded-MIME failure pause and cursor-expiry pause decisions
for newly running v2 workers; historical ADRs above record earlier shipped behavior.

**Decision (2026-09-20):** checkpoint schema v2 adds a reconciliation phase. Every
listing generation records the IDs actually received in a tenant/account inventory.
Only a complete, query-state-consistent listing whose unique ID count equals its
declared total can start reconciliation. Reconciliation hides absent local projections
in bounded batches, never deletes provider mail or retained evidence, then replays
changes from the pre-listing Email baseline. Query churn starts a fresh inventory
generation while preserving that baseline. Expired history starts a fresh full import;
legacy v1 checkpoints are safely reimported rather than trusted as certified inventories.

Within the existing 1 MiB raw bound, rejected MIME is retained byte-for-byte with a
hash, immutable failure receipt and current-message status in the same transaction
as the event and checkpoint. A quarantined update hides its old searchable projection;
later valid input or explicit deletion resolves current status without erasing the
receipt. Oversized downloads still fail closed, because their full bytes cannot yet
be retained. No binary execution, automatic reprocessing, send or mailbox writes.
An owner-scoped read-only sync-status endpoint exposes aggregate processing counts,
worker outcome and whether review is required; it never returns raw mail or credentials.
Synthetic corpus generation is offline-only and deterministic, with reserved invalid
addresses and no external model or provider calls.

**Tests:** synthetic multi-page imports, history expiry, list churn, incomplete or
contradictory inventories, crash/replay, poison mail mixed with good mail, foreign
tenant access, immutable receipts, batch bounds and end-to-end API evidence.

**Rollback:** additive migrations and v2 checkpoints require forward-compatible
workers; stop old workers before migration. Restore only through an explicit restore
workflow; do not down-migrate or discard inventory/evidence. Production cloud,
credential enrollment, retention cleanup and isolated binary extraction remain gates.

### ADR-018 — Consolidated hosting planning target (not provisioned)

Owner preference is fewer hosting accounts, not Microsoft-only application or
mailbox software. Prefer the same Azure hosting account/subscription as RealEstateOS
if that is the hosting home selected there, with isolated Email Brain resources,
identities, databases, secrets and budgets. Retain portable Python/PostgreSQL and
provider adapters. AWS remains an alternative if that is the actual existing
hosting home. No cloud resources, paid services, Entra app registrations, model
subscriptions or migration have been created or authorized by this planning choice.
Region, costs, identity design and deployment approval remain gates. See the
updated [hosting recommendation and sources](HOSTING_DECISION.md).

### ADR-021 — Read-only quarantine review surface

Related provider decisions are maintained in focused records:
[ADR-019: Gmail](adr/019_gmail_read_contract.md),
[ADR-020: Graph](adr/020_graph_read_contract.md), and
[ADR-022: injected IMAP](adr/022_imap_read_contract.md).

Expose current quarantine receipt metadata to an authenticated owner with
`email.evidence.read`, scoped to one account. Return at most 50 entries per page,
using receipt UUID keyset pagination; this is a live list, not a complete export
snapshot. Include fixed reason/parser version/hash and source ID, never raw MIME,
exception text, provider credentials or active attachments. Quarantine review is
informational: no dismiss, delete, reprocess or mailbox action capability is added.
Show this and aggregate sync state in the local owner UI. Clear visible evidence
on credential changes and reject stale asynchronous results after session changes.

Adversarial review additionally requires all persisted MIME projection strings to
be NUL-free and strict UTF-8 encodable before SQL. Decoder-produced invalid strings
must quarantine their unchanged source bytes. Both synthetic seed commands verify
unenrolled synthetic account status again inside each ingestion transaction; future
administrative enrollment must use the same account lock and stop worker callers.

Tests cover absent/foreign account identifiers, scope denial, bounded paging,
current-status filtering and the no-raw-data API contract. Production login,
audited reprocessing and browser accessibility acceptance remain gates.

## Additional accepted prototype decisions

[ADR-061 current-aware grouped retrieval](adr/061_current_aware_unified_search.md)
adds an explicit current-FileOS evidence mode to grouped KnowledgeCore search while
preserving retained-history compatibility and separate ranks.

[ADR-060 current FileOS search](adr/060_current_fileos_search.md) adds a cross-source
read over latest activated generations without silently redirecting compatibility or
unified search.

[ADR-059 private FileOS index operator](adr/059_fileos_index_operator.md) adds an
explicit authenticated build/activate and activation-only rollback command with exact
worker scopes. It does not schedule work or switch global search.

[ADR-058 immutable FileOS index generations](adr/058_fileos_index_generations.md)
adds completion-bound, deterministic lexical generations, append-only activation and
reactivation rollback. Mutation remains a trusted library operation until a narrow
operator command is separately accepted.

[ADR-057 read-only rebuild preview](adr/057_fileos_rebuild_preview.md) verifies current
normalized documents and chunks before any index-rebuild executor is authorized.

[ADR-056 completed-inventory reconciliation](adr/056_fileos_inventory_reconciliation.md)
adds exact per-run membership and immutable absence evidence without deletion or
search-visibility effects.

[ADR-055 FileOS completion and freshness](adr/055_fileos_completion_freshness.md)
separates imported/partial work from an immutable fully accounted run and exposes only
latest-complete source status.

[ADR-054 authenticated FileOS publication](adr/054_fileos_operator_publication.md)
adds a closed private operator configuration, exact worker scopes, idempotent snapshot
publication and repeated authorization checks without source effects.

[ADR-053 isolated FileOS documents](adr/053_isolated_fileos_documents.md) adds
source-revalidated PDF/DOCX/XLSX extraction through a dedicated networkless,
read-only container; it grants no source effects or OCR authority.

[ADR-052 grouped unified search](adr/052_grouped_unified_search.md) composes DataCore
evidence and KnowledgeCore assertions in separately ranked, independently bounded
layers requiring both scopes; it does not imply Email migration or synthesis.

[ADR-051 reviewed KnowledgeCore assertions](adr/051_knowledgecore_reviewed_assertions.md)
adds evidence-required entities, relationships, claims, events, projects, commitments,
corrections, bitemporal fields and lexical retrieval without automatic model writes.

[ADR-050 Brain API read slice](adr/050_brain_api_read_slice.md) adds source-neutral,
progressive search/evidence/content/change endpoints with separate scopes and bounded
untrusted content while preserving legacy Email API compatibility.

[ADR-049 FileOS text extraction](adr/049_fileos_text_extraction.md) adds bounded,
hash-reverified, read-only text/Markdown/HTML/CSV extraction with explicit outcomes
and live parity against the pinned FOS-Master donor.

[ADR-048 DataCore persistence](adr/048_datacore_persistence.md) adds bounded,
idempotent FileOS snapshot import, immutable source/evidence/provenance records,
deterministic chunks and tenant-isolated lexical retrieval without changing Email
tables or authorizing source writes.

[ADR-047 MasterBrain foundation](adr/047_masterbrain_foundation.md) establishes the
final product identity, shared core boundaries, non-destructive FOS-Master migration
protocol and first read-only DataCore hash/dedupe extraction.

[ADR-026 calendar attachments and format fixtures](adr/026_calendar_attachments_and_format_fixtures.md)
adds bounded searchable calendar source evidence and synthetic attachment/provider
format tests. It grants no calendar action or public-corpus import authority.

New accepted prototype decisions: [ADR-023 synthetic logical restore drill](adr/023_synthetic_restore_drill.md),
[ADR-024 opt-in local classification candidates](adr/024_local_model_classification.md),
and [ADR-025 reviewed virtual sender rules](adr/025_reviewed_rule_activation.md).
No production deployment, real model quality, mailbox effects or live-service
authorization is implied by these additive local/CI capabilities.

## Explicitly rejected for initial build

SQLite as multi-user source of truth; public database/model/MCP endpoints; vector-only retrieval; automatic send/delete; direct assistant SQL; direct model provider credentials; rules as executable code; graph database by default; whole-mailbox prompts; Git storage of email/live secrets.
