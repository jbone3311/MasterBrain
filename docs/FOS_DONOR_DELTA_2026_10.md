# FOS-Master donor delta after the pinned baseline

Reviewed 2026-10-20 UTC. The unchanged local donor baseline used by existing
MasterBrain parity tests is `jbone3311/FOS-Master@218d5caec2f20b9047fd3eb8e027dc671acf0c15`.
The donor's remote `main` is now `eb774fc254575a6ea1b5acba0c6ed75dd91eca76`,
11 commits ahead. This is a **review of later donor behavior**, not a replacement
of the pinned corpus, an extraction, or permission to change FOS-Master.

| Donor commit | Actual change | MasterBrain disposition |
|---|---|---|
| `a17b7dc`, `b267cac` | Hub hand-off-document placement instructions | Retain in donor; not a shared search or runtime primitive. |
| `21a1c49`, `02ca026` | Ignore a specific sensitive local HTML hand-off family | Retain donor rule; uphold MasterBrain's broader no-real-data and secret-scan gates, not just a filename ignore. |
| `3079c33` | Repoint report refuses to call a mass phantom/cross-domain disappearance confirmed when at least 10 rows and half a domain appear gone; a one-domain override is explicit | Compare with existing MasterBrain v1 mass-loss completion refusal and v2 historical `mass_loss` review flag. Add a synthetic cross-domain/partial-mount corpus before any current-state policy change. The donor self-test reads its live SQLite schema, so it was **not** executed here. |
| `6f961ae`, `b3935d1` | Final-audit HTML/PDF source validation and incomplete-report behavior | Preserve as a quality lesson for future derived reports: unreadable source is `not checked`, not a pass; never treat raw PDF bytes or the deliverable itself as validating evidence. The donor's report scripts are not DataCore search code and were not copied. |
| `6ca59fc` | Machine-readable audit output becomes one JSON document; unavailable checks appear as `NOT CHECKED` | Apply the principle to future MasterBrain source/index freshness display. Do not import hub session/report tooling. |
| `f6d6f6f` | Hub exchange/session telemetry corrections | Hub-specific; no MasterBrain runtime transplant. Source readiness must still be reported from MasterBrain's own ledgers. |
| `5d1fe9e` | Audited archive move to `<domain>/_Archive/<working-folder>/`, refusal to create new working-folder version piles, and default archive exclusion in the donor's file-name and hybrid search | Treat the directory policy as FileOS-specific. Preserve the move broker in operational FOS-Master; MasterBrain has no source-write authority for it. Design an explicit, versioned search-visibility policy before adapting the read behavior. |
| `eb774fc` | Body-text FTS now excludes exact `_Archive` path segments **before** `LIMIT`; `--include-archive` restores them | Adopt the current-working-file versus superseded-location distinction in a separately tested, source-scoped MasterBrain search tranche. Do not confuse this with extracting members of a ZIP/archive file. |

The new search behavior is a **visibility policy**, not a new indexing engine.
The donor already had FTS and optional local semantic search at the older pin;
these commits add archive-aware filtering to existing paths. The donor's
synthetic content-search, FTS, latest-only guard and archive tests passed
independently in a detached temporary checkout: **38 passed**. No domain file,
operational SQLite database, Dropbox root, or live source was read by those
selected tests. The old pinned donor checkout remains the parity authority.

Two visible donor limitations must not be copied into MasterBrain:

- `fos_tools.search` applies the archive rule in its SQLite FTS branch but not
  its JSON fallback. A fallback could therefore show superseded hits by
  default. MasterBrain must use one policy in every retrieval path or label a
  path as not policy-checked.
- `content_search.py --type` filters extension **after** SQL `LIMIT`, so
  different file types can consume result slots before the requested type is
  applied. A MasterBrain file-type facet must filter before ranking/limit.

See [ADR-263](adr/263_current_working_file_search_visibility_proposal.md)
for the proposed unified read contract. No new donor module is imported by
this review. Future parity must pin each exact donor file hash, compare
ordinary/current, archived, near-miss and limit-bound cases on both sides,
and separately account for newer donor changes before live shadow or cutover.
