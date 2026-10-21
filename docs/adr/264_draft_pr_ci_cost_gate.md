# ADR-264 — Cheap draft feedback, exact-head full merge gates

Status: accepted for synthetic repository CI; hosted behavior and effective branch protection still require verification.

## Context

The current PR cadence starts the complete PostgreSQL/container CI job, populated
restore drill and eight strict-runtime matrix jobs on every commit. The FileOS
benchmark also starts whenever its path filter matches the PR's aggregate diff.
That is useful for a merge candidate, but wasteful while a large PR is actively
being revised. GitHub Actions minutes are billed by job runtime. A prior green
commit is not evidence for a changed head, and a skipped required job can count
as success. Earlier PR-head jobs were blocked by the account payment/spending
gate; this ADR does not repair billing or claim a measured cost reduction.

## Decision

- Development PRs start as **draft**. Draft pushes run one no-PostgreSQL,
  no-Docker feedback job: Ruff, mypy, structural and documentation checks, and
  the first-party Brain browser contract. Contributors also run focused local
  synthetic tests for each changed slice. Draft feedback is not release proof.
- The existing required check names `gate`, `logical-restore` and
  `strict-runtime-gate` remain stable. Each aggregate runs on every PR event
  and fails for a draft; it cannot turn a skipped heavy job into a green merge
  check. The benchmark remains path-filtered and nonrequired.
- Marking a PR **ready for review** triggers the complete existing CI,
  populated restore and strict-runtime matrices on that exact candidate.
  Every later ready-PR push reruns them. Main pushes retain the full jobs.
  A PR may merge only after all three non-draft aggregates succeed on the
  current candidate, independent review/other release gates are satisfied,
  and GitHub's effective branch rule is verified. A manual `workflow_dispatch`
  run is diagnostic and does not replace PR checks.
- All four workflows cancel superseded in-progress PR runs. Main runs are not
  canceled. The restore drill and benchmark, which had no concurrency group
  before this ADR, key non-PR runs by `github.run_id`, so a queued main or
  manual run is never replaced by a newer one. `ci` and `strict-runtime` keep
  their pre-existing per-ref groups; GitHub may replace a *queued* main run
  there under rapid merges, which predates this ADR and is not changed by it. Do not use commit-message CI skipping, path filters on required
  workflows, or manual green status to bypass a failed exact-head check.
- A separate future ADR may adopt merge queue and `merge_group` after checking
  repository settings; this change does not assume a queue exists or alter
  branch protection. Local full tests are still required before calling a
  product increment verified; cheap draft checks do not reduce that standard.

## Safety, cost and rollback

The new aggregates intentionally show **red on drafts**; the only draft job
that tests code is `draft-feedback`. On ready PRs, the full jobs are unchanged
except for their job IDs and superseded-run cancellation. The stable aggregate
names preserve the existing `.github/branch-protection.json` contexts. No
secrets, live sources, migrations, product behavior or FOS-Master state change.

Validate YAML syntax, event/condition cases (draft, ready, main and failed
full job), local static/docs/browser checks, then observe one hosted draft and
one hosted ready transition with exact SHA and effective protection. PR #259's
first hosted draft run on `8573e62` proved feedback succeeded, all heavy jobs
were skipped, and all three required aggregates failed intentionally. The
effective `main` branch rule was read from GitHub and still requires those
three checks with administrator enforcement. The ready transition on the
same head `04f4ec0` then ran full CI, populated restore, strict runtime and the
FileOS benchmark, and all three required aggregates succeeded. Still unverified:
a hosted ready candidate with a failed full job (the aggregate logic requires
`success` exactly, so it should stay red) and any billed-minute comparison. If any required check is missing or unexpectedly green, keep PRs
unmerged and revert the workflow change in a reviewed PR; do not remove the
required contexts or administer a silent bypass. Compare actual billed runner
minutes before/after over a similar push cadence before claiming savings.
