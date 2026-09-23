# MasterBrain Build Progress

## Active checkpoint

**Checkpoint 5D — current-only archive-image OCR search proposal.** Work is tracked in
[GitHub issue #10](https://github.com/jbone3311/CW-EmailBrain/issues/10): the Claude
handoff requests an independent review of 5B persistence and a current search layer
on a separate branch and PR. The issue exists; Claude has not submitted a branch or
PR. Checkpoint 5C is accepted on `codex/masterbrain-foundation` in PR #4. Any 5D
implementation requires its own review and hosted gates before integration.

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
- Checkpoint 4P archive-member design `0195a53` and runtime `c7d2d27` passed the
  pinned donor 47-test suite/live golden, 2,525 hosted Python tests, real restricted
  archive-member invocation and
  [CI 35789652225](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35789652225)
  plus [restore 35789652166](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35789652166).
- Checkpoint 4Q archive-member text design `60903a9` and runtime `97aeab1` passed
  2,530 hosted Python tests, migration/forced-RLS/replay/current-fence tests and
  [CI 35792838710](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35792838710)
  plus [restore 35792838718](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35792838718).
- Checkpoint 4R private archive-member operator design `debd740`, runtime `257ab30`
  and hardened acceptance `d66de6e` passed 2,556 hosted Python tests, flat/nested
  forced-RLS publication, replay/revocation/fault tests, the real restricted member
  image, the pinned donor's 47 archive tests and six-case live parity corpus, plus
  [CI 35795580456](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35795580456)
  and [restore 35795580548](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35795580548).
- Checkpoint 4S current archive-derivative search design `d50db4c` and runtime
  `6c7b043` passed 2,556 hosted Python tests, forced-RLS current/stale transition,
  replay-deduplicated query and API/schema tests, the new migration and populated
  restore, all restricted worker containers, plus
  [CI 35796920249](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35796920249)
  and [restore 35796920235](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35796920235).
- Checkpoint 4T private archive-member preview design `7163334`, runtime `0a8c430`
  and deterministic non-bomb oversize-fixture correction `5befc42` passed 2,560 hosted
  Python tests, forced-RLS page/cursor/eligibility/replay/stale-parent tests, no-worker/
  no-source/no-receipt operator checks, all restricted containers, plus
  [CI 35799779137](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35799779137)
  and [restore 35799779396](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35799779396).
- Checkpoint 4U sealed archive-member batch design `b98b720` and runtime `1a3fd58`
  passed 2,568 local Python cases, 134 browser cases, the repository deployment gate,
  real PostgreSQL exact-plan publication/replay, all restricted containers, the pinned
  donor's 47 archive tests and six-case live parity corpus, plus
  [CI 35803130109](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35803130109)
  and [restore 35803130165](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35803130165).
- Checkpoint 4V archive-member PDF/Office design `ea6fd29`, two-worker orchestration
  `6680218`, receipt/selector `0210ad1`, publication `4d098fa`, private command
  `5bb1aa1` and real two-image gate `49b8383` passed 2,582 hosted Python tests, 134
  browser contracts, four chained restricted-image cases, populated restore and all
  prior container gates. PDF/DOCX/XLSX publication is exact, replayable,
  source-preserving and retained-history-only; hosted
  [CI 35810970182](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35810970182)
  and [restore 35810970151](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35810970151)
  are green.
- Checkpoint 4W current archive-document search design `9ba4b88` and runtime
  `7329ba9` passed 2,583 hosted Python tests with real PostgreSQL, 134 browser
  contracts, deployment, documentation and every restricted-container gate. Exact
  receipt/member/child/parent fencing, replay deduplication, tenant isolation and
  stale-parent removal are proven; hosted
  [CI 35816277436](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35816277436)
  and [restore 35816277514](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35816277514)
  are green. The pinned donor's 47 archive tests, six-case live archive parity and
  3,000-file hash/dedupe/extraction stress parity also passed locally without changing
  FOS-Master.
- Checkpoint 4X private archive-document preview design `ce2bf30` and runtime
  `1651c2b` passed 2,586 hosted Python tests with PostgreSQL, 134 browser contracts,
  deployment, documentation and all restricted-container gates. Exact PDF/DOCX/XLSX
  eligibility, sealed paging, replay-deduplicated publication state, tenant isolation,
  stale-parent refusal and non-consuming check mode are proven; hosted
  [CI 35818667860](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35818667860)
  and [restore 35818668296](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35818668296)
  are green.
- Checkpoint 4Y sealed archive-document batch design `2869aed` and runtime `87ea0d0`
  passed 2,594 hosted Python tests with PostgreSQL, 134 browser contracts, deployment,
  documentation and all restricted-container gates. Canonical format/key/order seals,
  check-mode non-consumption, sequential two-worker execution, item-two refusal and
  unchanged-plan replay are proven; hosted
  [CI 35821165890](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35821165890)
  and [restore 35821165886](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35821165886)
  are green.
- Checkpoint 4Z image/OCR inventory design `55b4854`, isolated runtime `cb6b940`,
  runtime binding `f21e534` and bounded scratch correction `512185b` passed 2,606
  hosted Python tests, 134 browser contracts, real byte-bound Tesseract OCR and every
  restricted-container gate; hosted
  [CI 35826212304](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35826212304)
  and [restore 35826212333](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35826212333)
  are green. The clean pinned donor passed 149 focused tests, 12 six-format golden
  cases and 120 generated parity stress cases; animated GIF is deliberately safer.
- Checkpoint 5A one-member archive-image design `6029240` and runtime `b17541d`
  passed 2,620 hosted Python tests, 134 browser contracts and the new four-case real
  archive-plus-image container chain; hosted
  [CI 35829326066](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35829326066)
  and [restore 35829325907](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35829325907)
  are green. Exact nested selection, 64-sibling exclusion, source preservation,
  blank OCR, animation policy and hash substitution refusal are proven.
- Checkpoint 5B archive-image persistence design `16d452a`, runtime `760a644` and
  grant/freshness/provenance correction `63b478d` passed 2,640 hosted Python tests,
  134 browser contracts, every restricted-container gate and populated restore;
  hosted [CI 35833506295](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35833506295)
  and [restore 35833506298](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35833506298)
  are green. The restore verified 72 tables / 238 rows. Exact, equivalent and
  concurrent replay, processor evolution, tenant/current fences, append-only RLS and
  image-specific provenance are proven.
- Checkpoint 5C private archive-image operator runtime `f658ace` passed 2,652 hosted
  PostgreSQL-backed Python tests, 134 browser contracts, every restricted
  worker/container gate and populated restore; hosted
  [CI 35836198307](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35836198307)
  and [restore 35836198414](https://github.com/jbone3311/CW-EmailBrain/actions/runs/35836198414)
  are green. This accepts one explicit image member/key command, not live-source or
  production operation.

## Current work

- Track the separate [Claude 5D workstream](https://github.com/jbone3311/CW-EmailBrain/issues/10)
  for independent review of 5B persistence and a proposed current-only OCR search
  layer. No Claude branch or PR has been submitted yet.

## Deferred by design

- Archive-image/OCR current search and batch scheduling until each separate contract
  is accepted.
- Automatic archive-document fan-out and scheduling.
- Automatic knowledge extraction, graph traversal and synthesis until reviewed
  known-answer evaluation exists.
- All file/mail effects and any FOS-Master cutover/retirement.

## Rule for updates

After each checkpoint, record exact commits, tests, donor baseline, CI/restore runs,
known limits, rollback and the next active checkpoint. Do not mark a later checkpoint
active while an earlier gate has unexplained failures.
