# Contributing

1. Read `PRODUCT.md`, `AGENTS.md`, and the relevant architecture/security documents.
2. Create an issue or ADR for changes to schemas, APIs, providers, permissions, retention, or security behavior.
3. Use synthetic fixtures only.
4. Keep changes small, typed, reversible, and covered by tests.
5. Run all validation commands in [AGENTS.md](AGENTS.md), including the repository
   gate and documentation link check, with the locked development environment.
6. Complete the pull-request template, including trust boundary, migration, rollback, telemetry, and data-handling impact.

No pull request may add automatic sending/permanent deletion or bypass schema, policy, approval, audit, or RLS controls without an explicit accepted ADR and independent security review.

Follow [documentation maintenance](docs/DOCUMENTATION_STANDARD.md): update feature
methods, implementation status, next work, operations and exact-commit evidence
alongside the relevant change. Keep proposed features distinct from executable
ones and preserve historical verification/source-research dates.
