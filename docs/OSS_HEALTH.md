# Open-source health snapshot

This is a dated research artifact, not a continuously refreshed popularity table.
The documentation refresh on 2026-09-20 preserves its original observations.
Re-run [oss_snapshot.py](../scripts/oss_snapshot.py) and inspect releases, licenses,
security advisories and substantive changes before adopting/upgrading a dependency.
Do not change the observation date without a new measured snapshot.

Observed 2026-09-19 Pacific / 2026-09-20 00:56 UTC. Counts come from the public GitHub
API and are preserved in [oss-snapshot.json](research/oss-snapshot.json), with
commit SHAs. Stars measure interest; subscribers are notification watchers, not
active users. Commits cover each default branch in the trailing 90 days, include
bots/merges, and cap at 1,000. They are not release counts or proof of quality.

| Project | Stars | Forks | Watchers | 90-day commits | Latest commit (UTC) | Judgment |
|---|---:|---:|---:|---:|---|---|
| [mail-memex](https://github.com/queelius/mail-memex) | 3 | 0 | 0 | 4 | 2026-07-02 | Tiny alpha; reference only; license file unverified |
| [notmuch](https://github.com/notmuch/notmuch) | 213 | 54 | 8 | 14 | 2026-08-23 | Mature upstream; GitHub mirror understates its community |
| [Talon](https://github.com/mailgun/talon) | 1,345 | 306 | 79 | 37 | 2026-09-15 | Established and recently active; parser pilot, not truth source |
| [IMAPClient](https://github.com/mjs/imapclient) | 562 | 95 | 11 | 20 | 2026-09-18 | Active mature protocol layer; preferred IMAP candidate |
| [imap-tools](https://github.com/ikvk/imap_tools) | 844 | 93 | 12 | 6 | 2026-09-14 | Maintained; ergonomic alternative; don't install both stacks |
| [sqlite-vec](https://github.com/asg017/sqlite-vec) | 8,118 | 348 | 69 | 0 | 2026-05-18 | Quiet recent default branch; optional edge experiment only |
| [pgvector](https://github.com/pgvector/pgvector) | 23,089 | 1,328 | 143 | 154 | 2026-09-08 | Strong default for vectors alongside Postgres, after need is measured |
| [Ollama](https://github.com/ollama/ollama) | 181,279 | 17,938 | 1,017 | 310 | 2026-09-19 | Strong local runtime option; pin versions and disable cloud routes |
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | 128,861 | 23,459 | 842 | ≥1,000 | 2026-09-19 | Very active alternative, more low-level integration work |
| [Graphiti](https://github.com/getzep/graphiti) | 31,013 | 3,154 | 174 | 106 | 2026-09-19 | Active, useful temporal provenance ideas; defer separate graph infrastructure |
| [Inbox Zero](https://github.com/elie222/inbox-zero) | 12,261 | 1,538 | 46 | 816 | 2026-09-19 | Active product patterns; nonstandard license terms mean no direct adoption |
| [Zero](https://github.com/Mail-0/Zero) | 10,811 | 1,334 | 42 | 0 | 2025-08-31 | Default branch quiet for over a year; stars alone do not justify dependency |

“Quiet” is an observation, not a declaration that an upstream project is abandoned.
notmuch's real upstream is [notmuchmail.org](https://notmuchmail.org/); assess its
release/mailing-list activity as well as the mirror. Review commits for substance:
CLA/dependency bots can make last-commit timestamps look healthier than feature work.

## Ideas to reuse without taking whole products

- mail-memex: stable evidence URIs, idempotent import, FTS and soft-delete patterns.
  Reject broad SQL tools and globally deduplicating by spoofable Message-ID alone.
- notmuch: fast tag/search/thread interaction. Do not make a local Maildir index
  the shared multi-tenant authority.
- Talon: quote/signature extraction behind a replaceable adapter; keep raw text and
  measure multilingual false trimming.
- Inbox Zero: manual label corrections should invalidate learned patterns; ignore
  the system's own filing messages when tracking replies. These are product lessons,
  not permission to copy restricted code. [Recent commit](https://github.com/elie222/inbox-zero/commit/2571ce4970aa5d024bb664a6739bd91b1172c367).
- Graphiti: event provenance, temporal validity and correction/supersession. Start
  with relational facts before adopting its graph/LLM orchestration.

See [OSS_EVALUATION.md](OSS_EVALUATION.md) for licenses and dependency decisions.
