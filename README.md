# CW-EmailBrain

Private, multi-user, evidence-first email intelligence infrastructure.

Email Brain incrementally synchronizes supported mail providers, preserves immutable evidence, performs deterministic classification and retrieval, and exposes bounded API/MCP interfaces to Grok, ChatGPT, Claude, and other clients. Models propose structured interpretations; policy-controlled code owns authorization and mailbox effects.

## Repository status

This repository is at **Phase 0 / executable architecture scaffold**. It includes:

- the full product and architecture pack in [`docs/`](docs/README.md);
- Factory-facing product and agent contracts;
- a dependency-light Python domain core;
- a safe declarative rule evaluator with tests;
- connector and event contracts;
- the initial PostgreSQL tenant/RLS migration;
- CI and a local deployment gate.

It deliberately does **not** contain production credentials, real email, provider OAuth apps, mailbox-write code, remote-model calls, or deployment configuration.

## Start here

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/deployment_gate.py
```

For development commands after installing the package:

```bash
python3 -m pip install -e .
```

## Binding documents

1. [`PRODUCT.md`](PRODUCT.md)
2. [`AGENTS.md`](AGENTS.md)
3. [`docs/SECURITY.md`](docs/SECURITY.md)
4. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
5. [`docs/DECISIONS.md`](docs/DECISIONS.md)
6. [`docs/FACTORY_HANDOFF.md`](docs/FACTORY_HANDOFF.md)

When these conflict, security invariants and explicit accepted ADRs win. A behavioral change requires documentation and test updates in the same pull request.

## First vertical slice

Implement one read-only provider connector through immutable evidence, normalization, PostgreSQL/RLS, lexical search, replay tests, metrics, and restore verification. Models, vectors, and mailbox writes are later increments.

## Data warning

Never commit real messages, credentials, OAuth tokens, database dumps, vectors derived from private mail, or unsanitized fixtures. Use synthetic test data only.
