# MasterBrain Build Progress

## Active checkpoint

**Checkpoint 4B — private Email bridge operator.** Work occurs on
`codex/masterbrain-foundation` in PR #4. Add a bounded, explicit command that maps
selected current Email evidence through the verified DataCore bridge, with private
configuration, exact worker scopes, non-consuming preflight and safe replay. It must
not scan implicitly, redirect Email search or gain mailbox/provider authority.

## Completed gates

- Foundation identity/architecture documentation and ADR-047.
- DC-001 read-only hash/dedupe extraction from pinned FOS-Master.
- Initial live-donor hash/name/both parity corpus.
- Hosted CI and synthetic PostgreSQL restore green at foundation baseline.
- Checkpoint 1 shared CLI, contracts, FileOS snapshots and 3,000-file donor parity
  completed in commit `73b58cb`; hosted CI and restore are green.
- Checkpoint 2 persistence/index completed in commits `20c5fb8` and `380761b`;
  hosted CI and populated logical restore are green.
- Checkpoint 3A text/Markdown/HTML/CSV extraction completed in `afebced`; hosted CI,
  donor parity and restore are green.
- Progressive Brain API read slice completed in `a06bcad`; hosted CI
  [35703242987](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35703242987)
  and restore
  [35703242983](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35703242983)
  are green.
- Final receipt revision `ee6b662` passed hosted CI and restore; it changes only
  measured documentation after the `a06bcad` runtime.
- Checkpoint 4 foundation revision `7d2afbf` passed hosted
  [CI 35706332421](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35706332421)
  and [restore 35706332264](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35706332264).
- Checkpoint 5 grouped retrieval revision `b60acd2` passed hosted
  [CI 35707895947](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35707895947)
  and [restore 35707895954](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35707895954).
- Checkpoint 3B isolated PDF/DOCX/XLSX revision `a6488c6` passed hosted
  [CI 35711403192](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35711403192)
  and [restore 35711403138](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35711403138).
- Checkpoint 3C authenticated publication runtime `e7f319c` plus tenant-isolated test
  correction `aaaf156` passed hosted
  [CI 35713893737](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35713893737)
  and [restore 35713893769](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35713893769).
- Checkpoint 3D whole-run completion/freshness runtime `1e0f87e` plus valid-conflict
  test correction `c12800f` passed hosted
  [CI 35716362139](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35716362139)
  and [restore 35716362094](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35716362094).
- Checkpoint 3E completed-inventory/absence reconciliation revision `77ccc81` passed
  hosted [CI 35718606046](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35718606046)
  and [restore 35718606093](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35718606093).
- Checkpoint 3F deterministic rebuild preview revision `0653a35` passed hosted
  [CI 35720358559](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35720358559)
  and [restore 35720358811](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35720358811).
- Checkpoint 3G immutable index generations revision `b715bf1` passed hosted
  [CI 35725616036](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35725616036)
  and [restore 35725615886](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35725615886).
- Checkpoint 3H private generation operator runtime `8a50eab` plus test-authorization
  correction `4716c88` passed hosted
  [CI 35727909717](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35727909717)
  and [restore 35727909764](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35727909764).
- Checkpoint 3I current FileOS search runtime `42606da` plus two-source stress revision
  `83f5747` passed hosted
  [CI 35729843020](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35729843020)
  and [restore 35729843019](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35729843019).
- Checkpoint 3J current-aware grouped retrieval revision `8bada56` passed hosted
  [CI 35731669724](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35731669724)
  and [restore 35731669604](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35731669604).
- Checkpoint 4A Email evidence bridge runtime `0eae4c4` plus least-privilege
  correction `bb4b45d` passed hosted
  [CI 35734147533](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35734147533)
  and [restore 35734147551](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35734147551).

## Current work

- Define the closed private operator input and exact current-version selection.
- Prove check mode, replay, authorization revocation, bounded batches and partial-run
  visibility without changing existing Email ingestion or search behavior.

## Deferred by design

- Legacy Office, archives, images and OCR until separate format/fault gates exist.
- Automatic knowledge extraction, graph traversal and synthesis until reviewed
  known-answer evaluation exists.
- All file/mail effects and any FOS-Master cutover/retirement.

## Rule for updates

After each checkpoint, record exact commits, tests, donor baseline, CI/restore runs,
known limits, rollback and the next active checkpoint. Do not mark a later checkpoint
active while an earlier gate has unexplained failures.
