# AI Model Strategy

Updated 2026-09-20. Current implementation is the opt-in, candidate-only
[Ollama library](LOCAL_MODEL_RUNTIME.md), tested with fake responses and not wired
into ingestion. No real-model quality result, embedding index or remote adapter
is claimed. All broader tasks below are requirements for evaluated future work.

## Policy

Every inference task has an escalation ladder:

```text
deterministic code/rules
  -> local constrained model
  -> stronger local model (optional)
  -> approved remote model
  -> human review for consequence, not just uncertainty
```

No task defaults to the largest/remote model unless its risk or measured quality requires it. Provider/model names are configuration; evaluation results select production versions.

## What code should do

MIME parsing, headers, dates, participants, domains, hashes/dedupe, provider threads, known sender/list rules, reply-state arithmetic, folder mappings, exact amounts/codes, retries, authorization, and mailbox effects. A model may suggest; it does not own these invariants.

## Local-model tasks

- Taxonomy classification and importance estimation.
- `needs_reply`/request/commitment candidate extraction.
- People/company/project candidate extraction and alias suggestions.
- New-content summarization and rolling-state patch proposals.
- Prompt-injection screening as one defense layer.
- Local embeddings and optional reranking.

Use schema-constrained generation, temperature near zero, fixed prompts, Pydantic/JSON Schema validation, enum allowlists, and retries capped at one repair attempt. Ollama supports JSON-schema structured outputs and recommends validation ([documentation](https://github.com/ollama/ollama/blob/main/docs/capabilities/structured-outputs.mdx)). `llama.cpp` provides a local server and schema-constrained response formats ([server docs](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)); pin and regression-test runtime versions because structured-output compatibility can change.

Candidate small-model families should be re-benchmarked at build time (for example, current Qwen, Phi, Gemma, or Mistral instruct models with commercially acceptable licenses). Do not encode a model choice in architecture or accept public benchmark scores as a mailbox-quality claim.

## Remote-model escalation

Escalate when one or more apply:

- calibrated confidence below task threshold;
- disagreement between rules/local models;
- high-value legal, financial, investment, or relationship nuance;
- complex drafting or cross-thread reasoning;
- local model fails schema/grounding checks;
- explicit user request for deeper analysis.

Remote calls receive the minimum evidence bundle: cleaned new text, necessary thread state, typed metadata, stable evidence IDs, and redactions. Account policy controls which categories/tenants may leave the environment. Log provider/model/version, disclosure class, hashes, tokens, latency, cost, and result status—not raw content in general logs.

## Confidence and consequence

Self-reported model confidence is not trusted. Calibrate probabilities on labeled data and set thresholds per action:

- Misclassifying Events vs Travel: low consequence.
- Missing `Needs Reply`: high recall requirement.
- Placing mail in `Review Delete`: very high precision requirement.
- Sending/deleting: model confidence can never replace approval in v1.

Use abstention. “Unknown/needs review” is a successful safe outcome.

## Extraction contract

All outputs include:

```json
{
  "schema_version": "email.extract.v1",
  "category": "investment",
  "needs_reply": true,
  "entities": [],
  "obligations": [],
  "facts": [],
  "evidence_spans": [],
  "abstain": false
}
```

The server adds provenance, model/prompt versions, and calibrated scores. Claims without valid evidence spans remain candidates and cannot become durable facts.

## Embeddings and retrieval models

- Compute embeddings locally by default; cache by normalized content hash + embedding version.
- Version dimension, tokenizer, chunker, normalization, and model together.
- Maintain lexical-only operation; vectors are an enhancement, not a dependency.
- Benchmark multilingual needs, names/numbers, long email, and local hardware.
- Re-embed via shadow index and swap only after recall/latency comparison.

## Drafting

Drafts are grounded in selected messages, thread state, recipient/tone preferences, and explicit user intent. The model returns subject/body plus cited evidence and uncertainty. It cannot send. Draft creation and send are distinct scopes and actions.

## Evaluation and routing loop

Build a privacy-reviewed gold set of synthetic plus consented/redacted real messages. Measure per-class precision/recall, calibration/error cost, schema validity, evidence-span correctness, injection resistance, latency, memory, energy/cost, and remote escalation. A challenger replaces a production model only after offline evaluation, shadow traffic, and rollback readiness. See [TESTING_AND_EVALS.md](TESTING_AND_EVALS.md).
