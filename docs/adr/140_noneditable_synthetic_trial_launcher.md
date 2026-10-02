# ADR-140: Install the synthetic trial non-editably

Date: 2026-10-02. Status: accepted for the fictional local trial only.

## Context and decision

The Mac trial launcher currently runs an editable project install. On this Mac,
macOS marked the generated `__editable__...pth` file hidden. Python 3.14 then
skipped that path file, so `email_brain.api` could not be imported even though
`uv sync` exited successfully. This is an environment-specific packaging failure,
not evidence of a database or Brain API failure. A separate attempt to start a
local PostgreSQL cluster inside the restricted tool sandbox failed because the
sandbox denied shared memory; the same fictional trial succeeded outside that
sandbox. Neither observation warrants changing database permissions or source
behavior.

The double-click launcher shall install the locked project and dev dependencies
non-editably, then run without a second implicit sync. This makes the installed
package, not an editable `.pth` path, the import source. Both commands must use
the same environment and supported Python 3.13–3.14 selection. The launcher
still accepts only the existing fictional trial arguments and starts a new
disposable PostgreSQL instance; it gains no live-source authority.

The ordinary developer `uv sync` workflow and the CI test suite remain editable
where supported. This decision is intentionally limited to the one-click trial
entry point. It does not claim that every macOS environment marks `.pth` files
hidden or that non-editable installation cures PostgreSQL sandbox restrictions.

## Validation and rollback

Check the launcher command contract and shell syntax, run the actual local
`--self-test` through the launcher on the affected Mac outside the restricted
sandbox, then run the repository quality gates. Rollback restores the editable
launcher invocation; no schema, evidence, source or FOS-Master changes occur.
