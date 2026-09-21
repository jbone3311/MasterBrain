# Local model classification runtime

Status: explicit library plus fake-server/output evaluations. Nothing is activated
in API, ingestion, CLI, scheduler or deployment. No Ollama daemon was contacted and
no model was installed or downloaded during implementation.
[ADR-024](adr/024_local_model_classification.md) defines this boundary.

## Integration API

[`local_model.py`](../src/email_brain/local_model.py) exports:

- `LocalModelConfig(model, expected_digest, local_only_attested=False)`: requires an
  explicit installed model tag, 64-character lowercase digest and verified isolation
  attestation. Cloud-looking tags, URLs and implicit tags are rejected.
- `OllamaLocalClassifier(config, transport=None)`: construction sends no requests.
  The injected transport is for synthetic tests; the default HTTP client uses only
  `127.0.0.1:11434`, ignores environment proxies, and refuses redirects.
- `classify(source_text)`: checks installed model metadata, then returns the existing
  validated `Classification` candidate with `Provenance`. Call `close()` afterward.
- `classify_code_first(source_text, deterministic=None, consequential=False,
  local=None)`: takes an existing trusted deterministic result first. Consequential
  policy skips all inference. Missing local runtime, failure, invalid output,
  unknown category, investment category and positive needs-reply candidates return
  human review. A valid low-consequence candidate returns code/local. Every result
  has `applied=False`; there is no remote path or action executor.

The caller must resolve tenant authorization and evidence scope **before** calling
this library, bind the returned source hash to an immutable evidence version, and
persist any candidate/receipt through its own authorized transaction. Classification
data and excerpts remain untrusted text even after schema validation. Deterministic
matching and the consequential flag must come from trusted code, not email JSON.

## Local-only boundary

Loopback does not prove local inference: an Ollama daemon can relay a cloud model.
The operator must disable cloud features, restart the daemon, and enforce OS/container
egress denial before attesting. Ollama documents `OLLAMA_NO_CLOUD=1` and its local-only
configuration. The adapter does not modify daemon configuration or firewall rules.
[Ollama local-only FAQ](https://docs.ollama.com/faq).

Every classification checks `/api/tags` for an exact tag/digest, positive local size
and unique match, then `/api/show` for local GGUF metadata. Remote-host/model metadata
is rejected before the email prompt is sent. There is no cache, pull, download,
provider credential or authorization header. Remote metadata in a completion is
also rejected, but that check cannot undo an earlier disclosure. The daemon's
metadata/digest is a claim, **not cryptographic runtime attestation**; preflight has
a possible model-change race, so trusted daemon isolation remains mandatory.
Ollama exposes upstream-host/model fields in its response types.
[Ollama response definitions](https://github.com/ollama/ollama/blob/main/api/types.go).

## Request and response controls

The fixed system instruction is independent of email. Email text is JSON-encoded
under `UNTRUSTED_EMAIL_DATA` in a separate user message. It cannot add API messages,
tools, hosts or parameters. This separation reduces risk; it does not prove a model
resists semantic prompt injection. Tool calls and extra message fields are rejected.

The existing Classification JSON schema is supplied as `format` and included in
the system prompt. Generation is non-streaming with temperature zero, thinking off,
bounded prediction/context options and immediate unload requested. Ollama documents
schema-constrained generation and subsequent Pydantic validation.
[Structured outputs](https://docs.ollama.com/capabilities/structured-outputs).

Limits: 8 KiB UTF-8 source, 32 KiB serialized request, 64 KiB response per request,
4 KiB classification JSON, 100 installed inventory entries, 20-second network
timeout with 2-second connect timeout, and a cooperative 60-second deadline across
preflight and inference. Byte limits do not guarantee token counts, RAM use or a
hard CPU/GPU wall-clock cutoff. Socket timeouts can overshoot the cooperative deadline;
production needs an isolated worker and cancellation/resource limits. The adapter
rejects compressed responses, duplicate JSON keys, nonfinite values, coerced primitive
types, wrong models, unfinished/truncated outputs and excerpts absent from the exact
source. It does not retry or repair output automatically.

Requests use only GET `/api/tags`, POST `/api/show`, and POST `/api/chat`; unsupported
runtime features fail closed. The chat API defines completion status, model name,
messages, tools and generation controls. [Chat API](https://docs.ollama.com/api/chat).

## Provenance, confidence and evaluation

Successful candidates carry model tag/digest plus source, output, system-prompt and
schema hashes and version identifiers. No raw prompt/output appears in repr/error
messages or library logs. Hashes can still fingerprint private content; do not put
them in public telemetry. Runtime version, hardware, tenant policy and durable
evidence IDs remain caller-level integration work.

`confidence_calibrated=False` is explicit. Self-reported confidence is neither an
accuracy guarantee nor permission to apply rules, classify away important mail,
send, delete or create drafts. Schema validity and an exact excerpt do not prove
the category or needs-reply judgment is correct.

[`test_local_model.py`](../tests/test_local_model.py) is an offline fake-server and
model-output harness: it checks expected route outcomes and defensive rejection for
malicious JSON/tools/excerpts, role delimiters, wrong/cloud models, server failures,
byte/deadline limits, redirects and code-first network avoidance. These tests measure
the **integration contract**, not a real model's precision, recall or injection
resistance. No real-model quality score is claimed.

Production requires a separately authorized, privacy-reviewed labeled corpus;
per-category/needs-reply precision and recall; abstention rates; human error costs;
real model/hardware latency; prompt-injection tests; runtime/model/license pinning;
and shadow evaluation before any state projection. The broader target entity,
obligation, embedding and draft features are not implemented here.

## Rollback

Stop calling the additive library or pass no local runtime to the orchestration
helper; work routes to human review. No database migration, model installation,
provider effect or deployment change needs undoing. Do not discard retained
evidence or future inference receipts as part of code rollback.
