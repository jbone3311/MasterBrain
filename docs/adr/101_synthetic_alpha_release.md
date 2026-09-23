# ADR-101 — Synthetic alpha and repeatable integration checkpoints

Status: accepted for the `0.2.0a1` test-only release candidate. This decision does
not authorize production deployment or FileOS cutover.

## Context

The MasterBrain migration has multiple independently tested FileOS and Email
increments, but top-level version/status language still describes only the first
donor primitive. A growing stack of isolated PRs is hard for another tester or
agent to evaluate as one product. Release history needs exact, reproducible
checkpoints without treating hosted CI as live-source acceptance.

## Decision

- Publish a synthetic alpha, version `0.2.0a1`, only after the cumulative branch
  passes the full hosted CI and populated restore drill and is merged to `main`.
  Tag that exact `main` commit `v0.2.0a1`. A version number in a branch is a
  candidate, not a release claim.
- Use short-lived feature branches and PRs. Record the base/head, changes, tests,
  limitations and rollback in the changelog/build receipt. Keep reviewable
  increments; merge only a passing exact head. Repeat the cycle for later alpha
  versions instead of accumulating an unbounded unintegrated branch stack.
- The alpha accepts only fictional/synthetic inputs and disposable PostgreSQL.
  Its supported evaluation surfaces are donor parity, the local CLI, the
  database-backed tests and the fictional Email reader. It is not a hosted
  multi-user service or authorization to connect live accounts or roots.
- Preserve FOS-Master at the pinned donor commit. Copy/extract with attribution,
  retain original golden outputs and explicit policy differences, and do not
  switch or retire FileOS until separate cutover acceptance.
- Database migrations are forward-only. Rollback of application behavior uses
  prior code/configuration or tested restore; never delete retained evidence,
  provenance or donor history to undo an alpha.

## Verification and remaining gates

Run lockfile sync, lint, types, unit/API/PostgreSQL tests, donor parity/stress,
documentation checks, worker/container checks and a populated synthetic restore
on the candidate head. Record failures and skipped database tests rather than
calling them passes. The production and FileOS cutover gates in
`RELEASE_ACCEPTANCE.md` remain independent and unsatisfied.
