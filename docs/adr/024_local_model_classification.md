# ADR-024 — Explicit local classification candidates

Accepted 2026-09-20 for a library and synthetic model-response harness only.
No daemon call, model download, remote inference, API activation or database change.

Use fixed loopback Ollama endpoints and an operator-selected installed model tag
plus expected digest. Require explicit local-only daemon/egress attestation, reject
remote model metadata before disclosing email, and never pull missing models.
Loopback alone cannot prove a daemon will not relay prompts to cloud models.

Send bounded untrusted text in a separate user data message under a fixed system
instruction and the existing Classification JSON schema. Reject tool calls,
truncation, unexpected models, malformed types and ungrounded excerpts. Return a
validated candidate and hashed provenance, never applied rules or mailbox effects.

Code-first orchestration skips inference for a supplied deterministic result.
Consequential work, local failure, invalid output and abstention go to human review;
remote calls stay unavailable. Claimed confidence is not calibrated or authority.

Tests use intercepted HTTP, fake metadata and fake model completions. Rollback is
to stop using this additive library; no persisted state or provider compensation.
Actual model quality, runtime pinning/isolation, memory/time limits, tenant policy,
durable inference receipts and production authorization remain integration gates.

Sources: [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs),
[chat API](https://docs.ollama.com/api/chat),
[local-only daemon setting](https://docs.ollama.com/faq),
[Ollama response types](https://github.com/ollama/ollama/blob/main/api/types.go).
