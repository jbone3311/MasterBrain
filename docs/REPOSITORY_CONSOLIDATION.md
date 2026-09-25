# Repository consolidation receipt

On 2026-09-25, `jbone3311/CW-EmailBrain` was renamed to
[`jbone3311/MasterBrain`](https://github.com/jbone3311/MasterBrain). The product
identity was already MasterBrain; this administrative change aligns the GitHub
address with it. The repository remains private with `main` as its default branch.
The internal `email_brain` package and compatibility command are not renamed by
this operation. FOS-Master remains the untouched FileOS donor.

Immediately before cleanup, `main` was
`c8c428bc61c17021394b67b489700123de2e3ea6`. GitHub's commit comparison
reported **zero commits ahead of `main`** for each of the 22 refs below. There
were no open pull requests. Their branch pointers were removed; the commits and
merged PR history remain reachable through `main`.

| Removed, already-contained branch | Removed, already-contained branch |
|---|---|
| `codex/cross-source-browser-trial-20260924` | `codex/masterbrain-alpha-integration` |
| `codex/masterbrain-alpha-main-receipt` | `codex/masterbrain-alpha-readiness` |
| `codex/masterbrain-archive-ledger-integrity` | `codex/masterbrain-confined-fileos-reads` |
| `codex/masterbrain-fileos-completion-coverage` | `codex/masterbrain-fileos-exclusion-ledger` |
| `codex/masterbrain-fileos-inventory-edges` | `codex/masterbrain-fileos-inventory-faults` |
| `codex/masterbrain-fileos-inventory-shadow` | `codex/masterbrain-fileos-junk-parity` |
| `codex/masterbrain-fileos-mass-loss-guard` | `codex/masterbrain-fileos-policy-identity` |
| `codex/masterbrain-fileos-root-binding` | `codex/masterbrain-foundation` |
| `codex/masterbrain-functions-roadmap-docs-20260925` | `codex/masterbrain-integrate-schema-safety` |
| `codex/masterbrain-migration-integrity` | `codex/masterbrain-safe-error-observability` |
| `codex/masterbrain-truncate-guards` | `codex/strict-sender-runtime-20260924` |

Two divergent branches were deliberately retained; neither was force-merged:

| Branch | Distinct history | Disposition |
|---|---|---|
| `review/factory-pass` (`91a9282`) | One commit ahead of `main`, 77 behind; closed, unmerged [PR #11](https://github.com/jbone3311/MasterBrain/pull/11) | Historical external review and migration proposal. Reconcile each finding against current migrations and tests before extracting any still-missing fix. Do not merge the stale branch wholesale. |
| `codex/strict-runtime-lock-prep-20260924` (`619e1c1`) | One commit ahead of `main`, 22 behind; old preparation workflow and ADR | Compare with the later strict sender-runtime gate and decide whether any workflow or ADR detail is still needed. Do not merge a potentially superseded workflow without review. |

Current branch set after cleanup: `main` plus those two retained branches. There
are no open PRs at this checkpoint. This consolidation does not establish product
acceptance, tag `v0.2.0a1`, authorize live sources, or permit FileOS cutover.

For a local checkout, point `origin` to the canonical address:

```bash
git remote set-url origin https://github.com/jbone3311/MasterBrain.git
```

Any external CI, application registration, webhook, bookmark, or collaborator
checkout using the old address should be reviewed and updated explicitly. The
historical `CW-EmailBrain` name in older decisions and local compatibility paths
is not a claim about the current product identity.
