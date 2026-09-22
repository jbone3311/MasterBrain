# MasterBrain Build Progress

## Active checkpoint

**Checkpoint 4P — hash-bound one-member archive read design.** Work occurs on
`codex/masterbrain-foundation` in PR #4. Define an isolated request that selects one
persisted member from one exact current archive version by inventory, safe locator,
expected hash and size. The response must be bounded to that one member and verified
by the parent. No automatic fan-out, normalization, persistence or search publication
enters this design.

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
- Checkpoint 4B private Email bridge operator revision `f600508` passed hosted
  [CI 35736010764](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35736010764)
  and [restore 35736010659](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35736010659).
- Checkpoint 4C current bridged Email search revision `743fb9e` passed hosted
  [CI 35737349912](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35737349912)
  and [restore 35737349873](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35737349873).
- Checkpoint 4D Email attachment occurrence/text bridge runtime `02eefb5` plus
  historical-parent fixture correction `aaf8df0` passed hosted
  [CI 35740735789](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35740735789)
  and [restore 35740736075](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35740736075).
- Checkpoint 4E approved Email PDF derivative bridge runtime `cd425d0` plus
  tenant-isolation fixture correction `c183a07` passed hosted
  [CI 35743436225](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35743436225)
  and [restore 35743436167](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35743436167).
- Checkpoint 4F private Email attachment/document bridge commands revision `6156b70`
  passed hosted
  [CI 35745615962](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35745615962)
  and [restore 35745615958](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35745615958).
- Checkpoint 4G layered current Email-family search revision `9b427e1` passed hosted
  [CI 35749176559](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35749176559)
  and [restore 35749176556](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35749176556).
- Checkpoint 4H grouped current-source search runtime `8da5b36` plus mixed-source
  assertion correction `7939674` passed hosted
  [CI 35751228402](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35751228402)
  and [restore 35751228447](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35751228447).
- Checkpoint 4I current-source coverage runtime `82012e9` plus state-transition stress
  revision `c2c97da` passed hosted
  [CI 35753479059](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35753479059)
  and [restore 35753479343](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35753479343).
- Checkpoint 4J private Email bridge preview runtime `4c3347c` plus current-version
  transition assertion correction `e9cf62f` passed hosted
  [CI 35756327120](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35756327120)
  and [restore 35756327113](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35756327113).
- Checkpoint 4K sealed Email message batch runtime `0fd8c35` plus legacy one-item
  idempotency-ordering compatibility correction `7ca0568` passed hosted
  [CI 35759175176](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35759175176)
  and [restore 35759175355](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35759175355).
- Checkpoint 4L preview design revision `5b26329` passed hosted
  [CI 35761452118](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35761452118)
  and [restore 35761451949](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35761451949).
- Checkpoint 4L attachment/document preview runtime `e3c0ee5` plus checkpoint-tracking
  revision `0c687e8` passed hosted
  [CI 35763636718](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35763636718)
  and [restore 35763636696](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35763636696).
- Checkpoint 4M sealed Email part-batch design `2825529` and runtime `c143e0c` passed
  hosted [CI 35774641187](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35774641187)
  and [restore 35774641102](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35774641102).
- Checkpoint 4N archive design `2aaeb26` and isolated inventory runtime `26473de`
  passed the pinned donor suite/live golden and hosted
  [CI 35780244211](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35780244211)
  plus [restore 35780244282](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35780244282).
- Checkpoint 4O archive persistence design `2d30728`, runtime `03dbb98` and explicit
  upgrade-list correction `08ccb68` passed hosted
  [CI 35783950712](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35783950712)
  plus [restore 35783950915](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35783950915).

## Current work

- Audit how a second isolated pass can select exactly one nested member without paths,
  ambient state or returning unrelated bytes.
- Define compressed-input/member-output bounds, persisted identity checks, nested
  traversal semantics and parent revalidation before implementation.

## Deferred by design

- Archive member-byte reads, archive-derived extraction/search, images and OCR until
  separate format/fault/persistence gates exist.
- Automatic knowledge extraction, graph traversal and synthesis until reviewed
  known-answer evaluation exists.
- All file/mail effects and any FOS-Master cutover/retirement.

## Rule for updates

After each checkpoint, record exact commits, tests, donor baseline, CI/restore runs,
known limits, rollback and the next active checkpoint. Do not mark a later checkpoint
active while an earlier gate has unexplained failures.
