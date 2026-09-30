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

This preview intentionally does not solve the v2 database shape. Before any
switch, define and test metadata-only persistence and freshness, an explicit
owner-reviewed v1-to-v2 baseline transaction, absence suppression across the
policy boundary, rollback, PostgreSQL/RLS/restore behavior, broader platform
and cloud-placeholder parity, authorized read-only live shadow, and bounded
cohort acceptance. A green synthetic preview alone cannot satisfy those gates.
