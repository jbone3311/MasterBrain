# Owner PDF review and cited results

Implemented synthetic local UI under [ADR-038](adr/038_document_owner_review.md).
Verification belongs to the exact-commit [build receipt](BUILD_RECEIPT.md), not
this workflow description. No live mailbox, hosted service or malware-safety claim.

## Before opening the screen

Use the existing [local setup](LOCAL_DEVELOPMENT.md) and fictional mailbox. The
server's optional `--document-processor-version` must match the separate
[PDF operator command](DOCUMENT_CONTROLLER.md)'s exact approved image. Without
that configuration, search/history still work but new PDF approval is unavailable.
The browser never configures images, runs Docker or receives worker credentials.

Human approval/cancel needs both review and evidence scopes and current owner
membership. Search needs search scope; evidence/history needs evidence scope.
Bootstrap tokens are local prototype credentials, not production login.

## Owner steps

1. Search for a fictional message. **Include approved PDF text** is off by default;
   ordinary message/text-attachment search remains available without it.
2. Choose **Inspect cited evidence**, then **Review this PDF** beside a deferred,
   eligible PDF. This selects the account and loads configuration/history only.
3. In **PDF attachment review**, inspect filename, account/evidence/receipt IDs,
   source/part hashes, processor and the `synthetic-unscanned-pdf-v1` policy.
4. Click **Approve this PDF** separately. It records one hour of consent for that
   exact source/processor/policy. It does not prove a worker is online or begin a
   browser-side extraction. A separately configured operator runs approved jobs.
5. **Refresh PDF history**, or **Refresh PDF job status** on a saved job. History
   replaces pages of at most 50 items; refresh from the beginning for new arrivals.
   There is no background polling or automatic approval.
6. **Cancel PDF approval** is available only while unfinished. A running reader
   may finish computing but cannot publish after cancellation. If completion wins
   the race, the screen displays completed rather than claiming cancellation.
7. For a completed job, choose **Inspect PDF result**. Read the extraction outcome
   and page excerpts, not just the job status. Partial/deferred/failed results stay
   explicit. Every result remains **unscanned**.
8. Opt into PDF text on a new search. PDF hits open **Inspect cited PDF pages**
   using their own document citation. Original message evidence remains separate.

Search is across authorized accounts, not filtered by the account input used for
import/processing history. Selecting a PDF explicitly selects its account. The
server rechecks current eligibility: a historical receipt can remain readable but
no longer qualify for new processing after a source/account change.

## Evidence and failure behavior

Page evidence is text only, at most 40 excerpts of 2,000 characters, with page
number, Unicode-character offsets, hash and truncation notice. Citation text is
not opened as a URL. No embedded PDF/HTML, images, scripts, password entry or raw
download. Hashes identify source bytes/excerpts, not document truth or malware safety.

The newest current extraction controls opt-in search. A historical job citation
may still resolve even if newer extraction failed or provider mail was deleted.
The screen labels the saved result/revision; it does not claim every historical
result is current. [Backend contract](DOCUMENT_PROCESSING.md).

- **Unknown approval outcome:** the server may already have saved it. Refresh
  history or explicitly **Retry same PDF approval request**. The current page
  retains the same UUID intent across same-account refresh/reselection. There is
  no automatic retry or silent new grant.
- **Page closed, token/account changed:** local evidence and intent memory clear;
  server grants do not. Reload history to reconcile before creating another grant.
- **Cancellation not confirmed:** refresh status; do not assume cancellation.
- **Disabled/stale configuration or invalid response:** approval controls remain
  unavailable until refreshed and validated. No image/policy fallback is selected.
- **Missing permission/source changed:** generic failure text, no provider/parser
  exception disclosure. Do not retry forever; inspect current history/source.
- **Partial/deferred extraction:** usable email body remains searchable. Original
  attachment receipt remains unchanged; it is not rewritten as successfully read.

## Implementation, tests and operations

[document_review.js](../src/email_brain/web/document_review.js) owns the document
channel and search/evidence rendering. Shared authentication/text-only helpers stay
in `app.js`; MIME controls retain separate state, queue and parser. Session, search,
view, selection and card generations fence both requests and late responses.
Same-session query changes clear selected PDF controls but not saved history.

[Node tests](../tests/web_documents.test.cjs) exercise the owner flow and hostile/
stale responses. [SQL/API bridge tests](../tests/test_document_ui_contract.py) render
actual database-backed API payloads in that DOM harness with known-answer extracted,
partial, deferred and failed results. This is not a real browser, scanner or actual
worker test. Existing actual-container/SQL tests verify the worker separately.

Existing document/search/evidence audit events cover API operations. No source text
or token enters new logging or browser storage. Re-run all three Node suites when
changing either script; the server must serve both compatible assets. They retain
the existing self-only content policy and no-store headers.

Rollback may deploy older compatible UI assets, but it does not cancel saved grants
or remove evidence. To stop processing, disable new server approvals, cancel
unfinished jobs and stop workers separately. No migration or downgrade is needed.
Browser/keyboard/screen-reader acceptance, hosted supervision, production identity,
scanner/live policy and broader extraction quality remain release gates.
