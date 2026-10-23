# MasterBrain — Lessons Log

Append-only. One entry per lesson a development session learns: what happened, what we
learned, what changed. Architectural decisions stay in `DECISIONS.md`; this log is for
operating lessons. Candidates worth sharing beyond this Product are staged in
`_SYSTEM/_KB/candidates/` and the Factory pulls them.


## L-MB-001 — Positional SQL/Python comparisons must pin byte-order collation (2026-10-23)

- **What happened:** PR #245's later-FileOS reads compared Python-sorted rows by position with
  rows read via `ORDER BY locator`. ~20 local "zero failed" receipts disagreed with the first
  hosted run: local test clusters used `C`, hosted CI uses `en_US.utf8`, where `~$`, `_` and
  mixed case sort differently. Every stored attempt became permanently "requires review".
- **What we learned:** a test database's collation is part of the test environment. A suite
  that only ever runs on `C` cannot see this class of bug.
- **What changed:** ADR-265 uses `COLLATE "C"` wherever SQL order is compared with Python order
  (prior art: migration 0059); the regression test uses a mixed-case hashed locator. Run local
  PostgreSQL suites on an `en_US.UTF-8` database (macOS ICU still differs from glibc in places).

## L-MB-002 — A committed hook command must never carry an absolute checkout path (2026-10-23)

- **What happened:** the Factory bind (PR #260) committed a PreToolUse hook pointing at the
  absolute path of the temporary checkout it ran in. Once that folder was gone, every tool call
  in every checkout of `main` failed, including reads, until PR #261.
- **What we learned:** a guard that errors blocks everything; an installer that writes absolute
  paths into committed config breaks every other clone.
- **What changed:** the hook runs `python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/cw_scope_guard.py`.
  Check any installer-written config for absolute paths before merging it.

## L-MB-003 — Parallel reviewers and CI reruns need isolation too (2026-10-23)

- **What happened:** four parallel review agents shared one scratch folder; one removed another's
  PostgreSQL `postmaster.pid` and may have stopped its server. Separately, rerunning *every*
  failed run on a branch restarted stale-commit runs whose shared concurrency group cancelled the
  head-commit runs.
- **What we learned:** give each agent its own data directory and port; rerun CI only for the
  head SHA.
- **What changed:** practice only — scope reviewer scratch space per agent; filter reruns by
  `headSha`.

## L-MB-004 — openpyxl read-only mode trusts the sheet's declared dimension (2026-10-23)

- **What happened:** an understated `<dimension>` let XLSX extraction skip cells and formulas yet
  report `extracted`. The FOS-Master donor has the same behavior.
- **What we learned:** a writer-supplied size hint is untrusted input; "complete" must be measured.
- **What changed:** ADR-265 resets the dimension, measures the real extent, rechecks bounds and
  iterates from A1. Recorded as an intentional difference from the donor.
