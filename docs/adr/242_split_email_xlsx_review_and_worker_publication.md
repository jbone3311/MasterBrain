# ADR-242 — Separate Email XLSX human review from worker publication

Status: implemented on an open PR with fictional PostgreSQL coverage and a local populated restore pass at `0c64f8b`. Actual-image execution, hosted exact-head CI and independent review remain unverified. No live account is authorized.

## Context

ADR-241 described a single principal holding both human review and DataCore publication scopes. The real token registry forbids that combination: `brain.source.ingest` and `brain.document.publish` are worker-only. The original service signature could pass a directly constructed context but could not be reached with a valid human API credential. Do not weaken the global role policy to make this feature pass.

## Decision

Keep ADR-239's exact synthetic attachment approval and ADR-240's isolated, immutable extraction result. A human owner with `email.review` and `email.evidence.read` may inspect bounded pages of the untrusted extracted text at `POST /v1/brain/email-xlsx-results/{approval_id}/inspect`. The human submits the exact text SHA-256, sheet count and cell count to `POST /v1/brain/email-xlsx-results/{approval_id}/publication-reviews`. This creates one tenant-fenced, append-only, one-hour review for the current result; it does **not** publish a document. Human review of a digest is not certification of every cell or financial truth.

Only a worker with `brain.source.ingest`, `brain.document.publish` and `email.evidence.read` may invoke the private `EmailXlsxDocumentBridge.publish` service with the review ID. Before publication it rechecks the unexpired approval and review, exact result, current source and attachment occurrence, approving/reviewing/worker owner membership, and optional caller reauthorization. Migration 0085 independently requires a matching human review for every new bridge receipt and verifies the resulting document body, digest and chunk count. Migration 0084 receipts, if any, remain readable without a review ID; no new unreviewed receipt is allowed. Review and publication are audited separately. No public worker-publish endpoint or live Fastmail access is introduced.

The owner-selected Librarian exchange remains `masterbrain_project_dossier_markdown_v1` (ADR-197/200). This XLSX path produces cited text, not a new Markdown schema or an automatically approved KnowledgeCore fact.

## Acceptance and remaining gates

Fictional PostgreSQL tests must exercise a real human token for inspect/review and a separate worker context for publication, source-grant/currentness hiding, SQL forgery and immutability, and old protected-table migration checks. The actual immutable image must run the approval → extraction → review → publication → search chain. Hosted exact-head CI and an independent populated restore must pass before merge. A first-party review screen, cell-level citations, full donor spreadsheet parity and any live-source pilot remain separate work.
