# Factory intake review and integration plan

Reviewed against private `jbone3311/CW-Factory` main on 2026-09-19. This is a
targeted source review, not an audit of every Factory tool or a claim its tests ran.
No Factory files, registries, databases, or other Products were modified.

## What is worth incorporating

| Factory source | Useful mechanism | Email Brain disposition |
|---|---|---|
| [STD-INTAKE-SSOT-001](https://github.com/jbone3311/CW-Factory/blob/main/_SYSTEM/standards/STD-INTAKE-SSOT-001.md) | Receive/hash → dedup → extract → facts → organize → embed → verify; every document accounted for; per-document derived-stage gates | Incorporated receipt accounting and explicit extracted/failed/skipped/deferred/pending outcomes; no vectors from filename-only stubs |
| [STD-INTAKE-REPORTS-001](https://github.com/jbone3311/CW-Factory/blob/main/_SYSTEM/standards/STD-INTAKE-REPORTS-001.md) | Receipt plus immutable event tables, hash chain, duplicate receipt links, supersession | PostgreSQL attachment receipts and append-only intake events; each occurrence retained; full supersession and archive-placement workflow deferred |
| [doc_extract.py](https://github.com/jbone3311/CW-Factory/blob/main/_SYSTEM/tools/doc_extract.py) | PDF text/tables; fast text-only route; optional Office/OCR capabilities; structured extraction output | Preferred adapter candidate for a separately sandboxed worker, not an API-process import |
| [archive_unpack.py](https://github.com/jbone3311/CW-Factory/blob/main/_SYSTEM/tools/archive_unpack.py) | Zip-Slip/symlink refusal, expansion/size/count/depth bounds, encrypted-member reporting | Reuse hardening contract and adversarial tests; archives remain explicitly deferred until the sandbox exists |
| [email_core.py](https://github.com/jbone3311/CW-Factory/blob/main/_SYSTEM/tools/email_core.py) | Normalized-message input independent of provider and destination; per-attachment outputs | Borrow adapter boundary; do not adopt the whole path-based orchestrator as a hosted multi-tenant runtime |
| [email_sanitizer.py](https://github.com/jbone3311/CW-Factory/blob/main/_SYSTEM/tools/email_sanitizer.py) | Untrusted framing, length caps, injection signals and secret-pattern checks | Useful defense-in-depth/eval input; pattern stripping is not proof of injection safety and must not replace raw evidence |
| [trusted_sender.py](https://github.com/jbone3311/CW-Factory/blob/main/_SYSTEM/tools/trusted_sender.py) | Exact-address/domain allowlists and unknown-sender review | A classification hint, never authorization. A spoofable From header cannot approve an action or establish identity |
| [email_with_attachments.py](https://github.com/jbone3311/CW-Factory/blob/main/_SYSTEM/tools/email_with_attachments.py) | Base64 file encoding without routing content through model context; missing input fails; structural no-send check | Use reference-only for future draft attachments. It **does not send mail** and is not an SMTP connector |
| [Intake OCR scoping](https://github.com/jbone3311/CW-Factory/blob/main/docs/specs/INTAKE_OCR_CORE_SCOPING.md) | Separate portable extraction primitives from Product-specific pipelines; explicit model routing and external-call audit | Adopt architecture; pursue a versioned, independently deployable extraction package through Factory review |

## Mismatches that must not be copied blindly

1. Older tool headers and PRIMITIVES-001 describe copied/hash-locked tools under
   ADR-014. Current [FACTORY.md](https://github.com/jbone3311/CW-Factory/blob/main/FACTORY.md)
   requires one live Factory and no copied governance. Treat the current contract
   as governing development. Hosted runtime packaging needs an explicit Factory
   decision; do not silently import `../CW-Factory` in production.
2. Factory's [Product Blueprint](https://github.com/jbone3311/CW-Factory/blob/main/docs/PRODUCT_BLUEPRINT.md)
   describes code outside Dropbox and Dropbox as the content surface. Jim requested
   Email Brain beside Factory in Dropbox. Keep that choice visible: source may be
   mirrored there, but **never** the live database, secrets, venv, or indexes. The
   observed local Dropbox Factory folder contains content/reports, not the verified
   GitHub checkout needed to bind. Do not claim a sibling bind has passed.
3. “ABSORB then delete carrier” and “intake ends empty” concern the drop-zone, not
   permission to delete mailbox messages or evidentiary attachments. Email Brain
   preserves source evidence while retained; safe relocation or completed receipt
   status is distinct from permanent deletion.
4. `doc_extract` dynamically discovers config/imports and can log exceptions/paths.
   The service adapter must pass explicit config, redact diagnostics, pin libraries,
   limit time/memory/output, and report TOOL_MISSING rather than empty success.
   PyMuPDF's license also needs review before enabling it in a proprietary product.
5. `archive_unpack` has useful preflight budgets; hostile data still needs actual
   streamed-byte enforcement and a process/container boundary. ZIP metadata alone
   and Python exceptions are not a malware sandbox.
6. A recognized sender and high model confidence are insufficient to file sensitive
   records into another Product. Cross-Product export needs explicit grants, a
   reviewed destination, idempotent receipt, and no direct peer-database writes.

## Gaps staged for Factory

See [`_FACTORY_CANDIDATES.jsonl`](../_SYSTEM/_MEMORY/_FACTORY_CANDIDATES.jsonl):

- reconcile stale primitive-distribution headers with the live runtime contract;
- define a deployable, versioned extraction package separate from development governance;
- add mandatory sandbox, capability/health report, budget and redacted error contracts;
- distinguish sender familiarity from authenticated sender authority;
- document evidence retention exceptions to carrier-delete intake language.

Records follow the six fields in
[STD-FACTORY-PROPOSAL-001](https://github.com/jbone3311/CW-Factory/blob/main/_SYSTEM/standards/STD-FACTORY-PROPOSAL-001.md).
They are staged requests, not accepted Factory changes. The Factory reader still
must validate and disposition them through a properly bound Product session.

## Source fingerprints

Git blob hashes observed: FACTORY.md `f2e4e052af82c3edb535256e46989a42623fbd59`;
doc_extract `1fef57dc79ec3ec80646010113dc727a1c5517e5`;
email_core `30d05970827c27a6ebec18a5cd178402c9d732a3`;
archive_unpack `8063bb459c7803cdec246ac317c4570753002206`;
email_sanitizer `4d54d6f02581fbd433423a01154752f5ebf7966a`;
email_with_attachments `47a39772b820e41abb056f6a8c8562aef46feada`.
These are review provenance, not vendored or executed dependencies.
