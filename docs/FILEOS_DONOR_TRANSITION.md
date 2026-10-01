# FileOS v1-to-donor policy transition preview

DC-002J is a private, read-only review aid for the policy gap between the
current publishable FileOS snapshot v1 and the pinned FOS-Master donor-policy
candidate. It is governed by [ADR-113](adr/113_fileos_policy_transition_preview.md).
It does not publish a v2 manifest, persist a baseline, infer deletion, change
search results, or switch FileOS. FOS-Master remains unchanged.

`preview_fileos_donor_transition(prior_manifest, root, source_id=...,
observed_at=...)` first validates the complete-shape v1 snapshot, the source ID,
strictly newer observation time, and identical private physical-root binding.
It refuses a wrong root **before** scanning that root. It then runs one bounded,
no-follow donor-policy candidate scan and returns a `publishable: false`,
`requires_review: true` report. A valid snapshot supplied to the function is
not, by itself, proof that the snapshot has a database completion receipt.

DC-002K adds `preview_fileos_completed_donor_transition(core, ctx,
prior_manifest, prior_run_id, root, source_id=..., observed_at=...)` for a
private database-backed review. [ADR-114](adr/114_completed_fileos_baseline_preview.md)
requires the exact v1 manifest/run to be the latest completed source run,
matching its intake receipt, policy and root hashes, every completed
item/version identity and terminal outcome balance. It checks once before the donor scan and again afterward;
a completion during the scan invalidates the preview. The operation requires
`brain.changes.read` and returns a `completed_baseline` identity, but it still
has `publishable: false` and no CLI/API or v2 publication authority. The
checks do not lock future completions after the report returns.

DC-002L adds an internal `record_fileos_transition_review(...)` path governed
by [ADR-115](adr/115_fileos_transition_review_packet.md). It performs one donor
scan, pairs that candidate with the completed-v1 preview, and seals the pair in
an immutable, tenant-scoped PostgreSQL review packet. Recording requires
`brain.source.ingest` plus `brain.changes.read`; an advisory-locked recheck
rejects a newer completed run between scanning and insertion. A repeated
packet ID with identical content is idempotent; a changed identity or duplicate
content under a different ID is refused. Packets have a 16 MiB bound and no
CLI/API route. Their stored canonical digest detects content changes in an
export, but a packet is **not** independent attestation of the filesystem.
No current search, freshness, absence or publication path reads this table.
The candidate's hashless rows remain deferred without fabricated versions.

DC-002M adds a private `DataCoreStore.fileos_transition_review(ctx, packet_id)`
read under [ADR-116](adr/116_private_fileos_transition_review_read.md). The
`brain.changes.read` summary returns only opaque identities, counts, fixed
blocker codes, timestamps, packet digest and whether the latest completed
receipt still matches the packet **at read time**. It omits root digests and
locators. `include_details=True` additionally requires `brain.evidence.read`
and returns at most 50 fixed-shape locator rows per ordinal page; a deferred
row still has no version or digest. Canonical-hash mismatch fails closed.
Historical packets remain reviewable if their v1 run is superseded. This is an
internal library path, not a Brain API or CLI route, approval or v2 publication.

DC-002N adds `DataCoreStore.stage_fileos_v2_inventory(ctx, packet_id, stage_id)`
under [ADR-117](adr/117_fileos_v2_staged_inventory.md). It projects the sealed
candidate into a separate, immutable PostgreSQL row ledger after verifying the
packet digest and latest completed-v1 receipt under the source lock. Hashed
rows retain real candidate versions and SHA-256; metadata-only deferred rows
retain size/reason with **NULL** version, digest and media type. Exclusions and
scan errors are recorded as distinct rows, and the database checks all four
counts at commit. One packet stages once, with idempotent same-ID replay. This
is a nonpublishing staging shape, not a v2 completion or transition approval;
v1 freshness, absence, indexes and search remain unchanged.

DC-002O adds an internal `FileOSV2TransitionReview.plan(ctx, stage_id)` and
`approve(human_principal, stage_id, approval_id, ...)` under
[ADR-118](adr/118_fileos_v2_transition_review_approval.md). The compact plan
revalidates the sealed packet, candidate, staged rows, prior item ledger,
latest v1 receipt and root binding. It exposes counts and fixed blocker codes,
not locators. Approval requires a human owner with the separate transition
review and evidence scopes, the exact canonical plan digest and both count
maps. Prior snapshot/scan errors, unobserved and error-covered prior items
block approval; deferred and excluded observations are visible and explicitly
acknowledged, never interpreted as deletion. One immutable receipt records
the decision. This remains synthetic/disposable, private and nonpublishing;
it is not the future v1-to-v2 baseline transaction or a live-root attestation.

DC-002P adds a private `FileOSV2BaselineVerifier.verify(worker, stage_id,
approval_id, verification_id, root)` under
[ADR-119](adr/119_fileos_v2_baseline_verification.md). It consumes the exact
human approval only after rechecking the latest v1 receipt and matching a
fresh donor-policy scan of the specified root to every staged row, including
hashless deferrals and exclusions. A mismatch or source change refuses the
operation. Its immutable receipt records historical verification, not a v2
completed run: v1 freshness, absence, search and policy remain unchanged.
There is no API/CLI route or live-source/cutover acceptance.

DC-002Q adds a private `FileOSV2EvidencePreparer.prepare(worker, stage_id,
approval_id, verification_id, preparation_id, root)` under
[ADR-121](adr/121_fileos_v2_prepared_evidence.md). It rechecks the current v1
receipt and historical review/verification, then performs another exact
source-bound donor scan under the source lock. Only hashed rows receive
policy-scoped shared DataCore versions and source-bound evidence. An immutable
mapping retains each donor candidate version ID; it does not reuse that ID
because v1's immutable version metadata includes mtime. Deferred, excluded
and error rows receive no invented evidence. The preparation receipt does
not update a current pointer, complete v2, create absence, activate an index,
change search or authorize a FileOS switch. No API/CLI or live-source use is
accepted.

DC-002R adds a private `FileOSV2BaselineAuthorizer.authorize(human, stage_id,
approval_id, preparation_id, authorization_id, ...)` under
[ADR-123](adr/123_fileos_v2_baseline_authorization.md). A human owner with a
distinct authorization scope and evidence-read permission binds the exact
reviewed plan, count maps and prepared evidence digest after a latest-v1
recheck. The immutable receipt authorizes a future baseline completion attempt,
not publication by itself. It makes no fresh filesystem claim and changes no
current pointer, search, freshness, absence or FileOS operation. There is no
API/CLI route or live-source acceptance.

Every prior v1 item gets exactly one state:

| State | Interpretation |
|---|---|
| `unchanged` | Donor hash and size yield the same source version ID |
| `changed` | Same locator, different hashed source version ID |
| `deferred_prior` | Donor sees it without a digest (`no_hash`, `dataless`, or `oversize`) |
| `excluded_prior` | Donor policy explicitly excludes it or an ancestor directory |
| `error_covered_prior` | Donor scan error covers it or an ancestor directory |
| `unobserved_prior` | No donor ledger accounts for it; **not deletion evidence** |

Donor-only hashed items are reported separately; on a real root they might be
new files or policy differences, and the preview does not claim which.
Candidate errors, prior snapshot errors, and prior items no longer hashed
under donor policy are explicit blockers. Even a report with no blockers still
requires review and cannot authorize v2 publication or completion. The report carries prior policy
SHA, donor policy, root binding, counts and private locator-level diagnostics;
keep it in the same protected operator boundary as the source inventory.

The fictional pinned-donor 3,000-file comparison has 3,006 v1 items:
3,002 unchanged hashes and four prior items excluded by donor policy. The donor
has two additional hashed items that v1 did not publish. These six policy gaps
are explicit and blocked, not silently normalized away. Focused tests also
cover changed content, new/unobserved items, metadata-only rows, directory
errors, symlink errors, source/root/time mismatch and no source effects.
The same comparison passes at the largest valid synthetic v1 inventory:
9,994 stress files plus six fixed v1 items, exactly the 10,000-item manifest
bound. A request for 9,995 stress files is refused before scanning the donor;
the bound is not relaxed to make the stress test pass.

## Remaining publication gate

The staged row model, hashed-evidence preparation and owner authorization solve
part of v2 intake, but not v2 freshness or publication. Before any switch,
define and test a fresh, source-locked v1-to-v2 baseline completion transaction,
absence suppression across the
policy boundary, rollback, PostgreSQL/RLS/restore behavior, broader platform
and cloud-placeholder parity, authorized read-only live shadow, and bounded
cohort acceptance. A green synthetic preview alone cannot satisfy those gates.
