# ADR-153 — Require stable checks before merging to main

Status: accepted for repository governance; protection must be verified on GitHub.

## Context

All three broad gates run on pull requests and pushes to `main`, but `main` has
had no branch protection. A merge could therefore land while a full gate was
still running. The strict-runtime workflow fans out by Python version; its
matrix job names are not a stable single required-check target.

## Decision

- Add a `strict-runtime-gate` job that succeeds only when both supported and
  unsupported interpreter matrices succeed. It runs even after a failed or
  cancelled matrix, so an incomplete matrix cannot produce a green aggregate.
- Require `gate` (full CI), `logical-restore` (populated synthetic restore),
  and `strict-runtime-gate` on pull requests to `main`, with the branch current
  with `main`. Apply the rule to administrators as well. Refuse force pushes and
  deletion; retain merge commits and repository history.
- Do not require the path-filtered benchmark: it does not run on every PR.
  Do not claim that these synthetic gates prove a live provider, hosted privacy
  boundary, FileOS cutover, or a human review of the diff.
- Keep the required approvals count at zero for the present single-maintainer
  cadence. A human still decides whether to merge; larger changes should seek
  independent review. Changing that policy needs explicit owner agreement.

## Verification and rollback

First run the new aggregate job on its own PR. Then apply the versioned
`.github/branch-protection.json` settings and inspect the effective GitHub
protection. Prove an incomplete PR cannot merge and verify a green PR can.
Record exact PR/check results in the build receipt. If the rule unexpectedly
blocks healthy PRs, investigate the check name or workflow trigger; a temporary
administrator rule change must be recorded publicly, not silently bypassed.
This is repository governance only; no product code, data or FOS-Master state
is modified.
