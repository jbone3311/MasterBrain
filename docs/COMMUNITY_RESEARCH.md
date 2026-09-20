# Community evidence and what it changes

Reviewed 2026-09-19. Community reports are anecdotal and sometimes promotional;
they supply failure modes and test ideas, not security or model-quality guarantees.

| Discussion | Reported lesson | Product response |
|---|---|---|
| [Local classifier with n8n](https://www.reddit.com/r/LocalLLM/comments/1qem1po/we_finetuned_an_email_classification_model_so_you/) | Small specialized local classification can avoid external model calls; author-promoted demonstration | Benchmark a narrow local classifier against our gold set; don't import its claimed accuracy |
| [Processing email for context](https://www.reddit.com/r/LocalLLaMA/comments/1qg4d4t/what_we_learned_processing_1m_emails_for_context/) | Structured context, identity and attachments matter beyond body embeddings | Preserve sender/time/thread/attachment provenance and evidence-backed state |
| [Large local archive](https://www.reddit.com/r/LocalLLM/comments/1smigc3/local_gemma_4_31b_is_surprisingly_good_at/) | Thread length, quoted text and hand-labeled evaluation can matter as much as model choice | Keep a private gold set; version parsers/prompts; bound new-content extraction; retain raw fallback |
| [Local spam classification](https://www.reddit.com/r/LocalLLaMA/comments/1v4d55h/using_a_local_llm_to_check_for_spam_on_your_own/) | A user observed an invoice misclassified as spam | Protected financial classes; shadow mode; Review Delete only, no permanent deletion |
| [Complex email threads](https://www.reddit.com/r/LocalLLaMA/comments/1r97toz/how_do_you_handle_very_complex_email_threads_in/) | Relevant messages need surrounding conversational context | Retrieve bounded thread neighbors, diversify duplicates, cite exact versions rather than whole-mailbox prompts |
| [Earlier Gmail indexing experiments](https://www.reddit.com/r/LocalLLaMA/comments/18r1e34/) | Provider search and normalized fields can solve many queries without elaborate agents | Exact filters and FTS first; semantic retrieval only after measured misses |

Technical decisions are verified against provider/OSS documentation in the connector,
security and model strategy files. We do not adopt a package because a Reddit post
advertises it or treat “local” as proof that no component phones home.

## Evaluation additions

Invoices disguised as promotions; long quoted threads; forwarded messages; malformed
charsets; mixed-language requests; user versus system-generated moves; attachment
duplicates; nested/oversized archives; stale obligations; and prompt injections
asking to exfiltrate evidence or override instructions. Use synthetic adversarial
fixtures first, then a consented private corpus outside Git.

The [Microsoft LLMail-Inject challenge](https://github.com/microsoft/llmail-inject-challenge)
is a stronger technical reference for adversarial email retrieval/injection tests;
its examples inform eval design, not a claim our current tests defeat all attacks.
