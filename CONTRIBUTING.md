# Building Email Brain

Updated 2026-09-21. Private product; this guide organizes existing engineering and
release requirements. It grants no access to real mail, cloud spending, remote
inference, mailbox actions or Factory-owned configuration.

## Start with the product, then the existing code

Read [PRODUCT.md](PRODUCT.md) and [AGENTS.md](AGENTS.md), then the
[game plan](docs/GAME_PLAN.md), [current status](docs/IMPLEMENTATION_STATUS.md) and
[code map](docs/CODE_MAP.md). Use the [Factory handoff](docs/FACTORY_HANDOFF.md) for
the next bounded assignment. Do not generate another scaffold: ingestion, search,
rules, recovery and the synthetic PDF backend already exist.

The [local-development guide](docs/LOCAL_DEVELOPMENT.md) covers disposable
PostgreSQL, private bootstrap credentials and loopback serving. The
[test-mailbox guide](docs/TEST_MAILBOX_PLAN.md) covers fictional messages, actual
attachment formats, answer keys and repeatable replay. No mail-provider account or
model subscription is needed for that test path. Live state stays outside Git and
Dropbox; never place production credentials in examples or screenshots.

## Make one independently verifiable increment

1. Choose an existing [backlog ID](docs/BACKLOG.md). State the user outcome,
   included work and explicit exclusions in the GitHub build issue.
2. Read security, architecture, data model, decisions and the applicable contract.
   Add an ADR **before implementation** when required by AGENTS.md; a documentation
   edit is not authorization to change a permission or live-data boundary.
3. Preserve existing user changes. Implement the smallest complete path, with
   failure/retry/authorization behavior, not just the happy-path endpoint.
4. Add synthetic positive, negative and concurrency/recovery tests as appropriate.
   A fake processor tests orchestration; actual-container tests test the reader's
   execution boundary. Identify both instead of substituting one for the other.
5. Update docs with the implementation: status, methods, contract, next assignment,
   operations/rollback and changelog. See the [maintenance checklist](docs/DOCUMENTATION_STANDARD.md).
6. Run the checks below; publish exact-commit evidence. Use the PR template and
   [release acceptance record](docs/RELEASE_ACCEPTANCE.md) for review/promotion.

## Repository checks

```sh
uv sync --locked --extra dev
uv run ruff check .
uv run mypy src
uv run pytest -q
node --test tests/web_session.test.cjs tests/web_processing.test.cjs tests/web_documents.test.cjs
node --test tests/web_reader.test.cjs
uv run python scripts/deployment_gate.py
uv run python scripts/check_docs.py
git diff --check
```

Database tests require the disposable setup described in local development.
Missing PostgreSQL produces explicit skips, not successful database acceptance.
[CI](.github/workflows/ci.yml) exercises real PostgreSQL and both restricted images;
the [restore workflow](.github/workflows/restore-drill.yml) is a separate proof.
Inspect results for the commit actually under review. A prior green run does not
certify a changed migration, image or test suite.

The documentation gate includes hidden GitHub templates and supported local section
links, not just file existence. See its [scope and limitations](docs/DOCUMENTATION_STANDARD.md#automated-check-scope).
When changing it, also run `uv run pytest -q tests/test_check_docs.py`. Link checks
do not replace reviewing feature claims against source and actual test evidence.

## Before requesting review

- Explain method, source/permission boundary, compatibility and failure behavior.
- Include test command, exact commit, environment, pass/fail/skip counts and links.
- State remaining live-provider, identity, scanner, model-quality and hosting gates
  relevant to the change; do not call the product finished because tests pass.
- Verify dependencies/lockfile changes and assess supply-chain/license impact.
- Keep evidence immutable; never modify an already-published migration to hide an
  upgrade problem. Document forward repair or a tested restore path.
- Scan for secrets/private content. Attach only fictional examples and content-free
  diagnostics; do not paste raw production exceptions or provider credentials.

Factory must perform its own registration/bind/audit. Product code and docs cannot
declare that audit passed or modify Factory's registry by implication. Park owner
choices in [OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md); safe synthetic work can continue.

No pull request may add automatic sending/permanent deletion or bypass schema,
policy, approval, audit or RLS controls without an explicit accepted ADR and
independent security review. Preserve historical verification and research dates;
explain proposed features separately from executable ones.
