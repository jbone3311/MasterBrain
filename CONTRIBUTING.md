# Contributing

1. Read `PRODUCT.md`, `AGENTS.md`, and the relevant architecture/security documents.
2. Create an issue or ADR for changes to schemas, APIs, providers, permissions, retention, or security behavior.
3. Use synthetic fixtures only.
4. Keep changes small, typed, reversible, and covered by tests.
5. Run `python3 scripts/deployment_gate.py` before opening a pull request.
6. Complete the pull-request template, including trust boundary, migration, rollback, telemetry, and data-handling impact.

No pull request may add automatic sending/permanent deletion or bypass schema, policy, approval, audit, or RLS controls without an explicit accepted ADR and independent security review.
