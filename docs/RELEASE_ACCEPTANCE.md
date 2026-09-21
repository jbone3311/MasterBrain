# Release acceptance and evidence

Updated 2026-09-21. This checklist consolidates existing PRD, security, roadmap and
Factory handoff requirements. It does not approve a deployment or add runtime
permissions. The current product is a synthetic-data prototype, not a live release.

## Three different decisions

| Decision | Required evidence | What it does not authorize |
|---|---|---|
| Merge a bounded increment | Contract/ADR where required, reviewed implementation, relevant tests, docs and compatibility/rollback notes | Real mail, paid services, remote disclosure or production promotion |
| Accept a disposable live pilot | Explicit provider/account and environment authorization; identity/storage/scanner coverage policy; actual conformance, restore and operator acceptance | Arbitrary user accounts, sharing, write scopes or broader rollout |
| Release production capability | Every applicable launch gate below, named accountable reviewers, exact artifact/configuration and recorded acceptance | Unreviewed future scope or a claim that every planned feature exists |

## Gate register for the first read-only service

“Existing evidence” describes a foundation, not a checked production gate. Record
pass/fail/pending/not-applicable with rationale for each proposed release.

| Gate | Existing evidence | Still required for live promotion |
|---|---|---|
| Product scope and consent | PRD, roadmap, parked owner choices | First account/backfill, region, budget, retention and document coverage decisions |
| Provider integrity | Synthetic Fastmail HTTP-to-SQL; offline Gmail/Graph/IMAP contracts | Enrolled disposable provider, cursor expiry/moves/outages and sustained reconciliation |
| Identity and isolation | Bootstrap owner/scopes, forced RLS, composite keys and negative tests | Production OIDC/MFA, lifecycle/revocation, rate limits; grants before any sharing |
| Source durability | Immutable evidence, encrypted local objects, atomic cursors | Hosted Blob/KMS/IAM, separately recoverable keys and accepted retention/purge |
| Document safety and usefulness | Restricted MIME/PDF containers; synthetic PDF approval/result/search | Owner/operator workflow, accepted scanner/live policy, deployed isolation and quality on supported inputs |
| Independent operation | Worker libraries, MIME operator command, bounded retries/fences | Hosted supervision, enrollment, restarts/soak, alerts and responsible operator |
| Search and evidence | Authorized FTS, immutable citations, opt-in PDF results | Representative held-out retrieval and latency results at accepted corpus size |
| Backup and disaster recovery | Disposable SQL/object restore with hashes/search/RLS | Managed PITR/offsite recovery, key loss scenario, measured production-like RPO/RTO |
| Supply chain and governance | Locked builds, lint/types/tests, recorded scans, Factory proposal | Release SBOM/license/advisory/signature gates and independent Factory bind/audit |
| User acceptance | Local UI and Node DOM-contract tests | Real browser, keyboard/screen-reader, operational failure and owner acceptance |

An initial read-only pilot can explicitly defer an unsupported document format;
it cannot silently count it as extracted. Models, vectors, team sharing, MCP and
mailbox effects are separate milestones, not prerequisites invented to block the
first lexical-search pilot. If enabled later, each needs its own acceptance evidence.

## The metrics must say what they measured

Targets remain in [PRD.md](PRD.md); record results against a versioned test set.

- **Coverage:** received, preserved, held, searchable body, extracted document,
  unscanned/scanned and interpreted counts separately. Queue completion is not a
  document-quality metric.
- **Quality:** top-5 retrieval success, correct citations, extraction correctness,
  Needs Reply/Review Delete precision and recall, abstention and correction rate.
  Unimplemented features are “not evaluated,” never assigned a perfect score.
- **Reliability:** cursor lag, duplicate/replayed events, retries, stale publication
  denials, provider drift, queue age and duration of outage/soak scenarios.
- **Cost/performance:** p50/p95 latency, corpus size, concurrency, CPU/memory,
  storage growth and model-disclosure rate/cost when inference is actually enabled.
- **Recovery/security:** restore time, recoverable point, hash/citation integrity,
  authorization negatives, revocation and independent review findings.

Report sample size, fixture origin, seed/version, runtime/model/image versions,
environment and known limitations. A generated known-answer corpus proves expected
behavior on those cases, not accuracy on the owner's entire mailbox.

## What a release record contains

Create the record with the proposed change/release; do not fill it with assumed passes.

1. User-visible outcome, exclusions, backlog IDs and governing ADRs.
2. Exact Git SHA, container digests, lockfile, schema/migration level and compatible
   API/worker versions; private environment/configuration reference without secrets.
3. Authorization for any live accounts, resources or disclosure, and the accepted
   data classes/region/budget/retention. An issue title is not that authorization.
4. Checks and linked results: local skips, real SQL, actual containers, browser,
   restore, live conformance, load/soak and quality evidence separately.
5. Each applicable gate's disposition, named reviewer/owner and unresolved risks.
6. Rollout/stop criteria, exact rollback or forward-repair procedure, migration
   compatibility and treatment of outstanding processing approvals after restore.
7. Operational owner, alerts, incident path, recovery artifacts/key custody and
   post-release verification. Do not store backup archives or keys in this record.

Latest verified builds are in [BUILD_RECEIPT.md](BUILD_RECEIPT.md). Follow
[DEPLOYMENT.md](DEPLOYMENT.md), [OPERATIONS_RUNBOOK.md](OPERATIONS_RUNBOOK.md) and
[RESTORE_DRILL.md](RESTORE_DRILL.md) for the corresponding operational contracts.
