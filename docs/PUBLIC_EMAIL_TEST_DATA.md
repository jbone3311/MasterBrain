# Public email test data: selection and adoption policy

Reviewed 2026-09-20. This is a source shortlist and proposed adoption gate, not an
import receipt. No public email corpus, message bodies, attachments or archives
were downloaded, vendored, replayed or used to claim a passing test in this review.
Only publisher documentation, repository directory listings and license information
were inspected. Links to moving branches below are discovery links, not approved pins.

For the proposed believable continuous feed, use [TEST_MAILBOX_PLAN.md](TEST_MAILBOX_PLAN.md).
Its primary strategy is known-answer fictional scenarios plus selected public
format references—not random real correspondence imported into the repository.

## Additional file collections and test tools

- [Apache Tika Office/email fixtures](https://github.com/apache/tika/tree/main/tika-parsers/tika-parsers-standard/tika-parsers-standard-modules/tika-parser-microsoft-module/src/test/resources/test-documents):
  parser regression references, subject to per-file provenance/rights review.
- [EDRM file-format dataset](https://edrm.net/resources/data-sets-2/): publisher lists
  381 files across 200 formats including Excel, Word and PST. This is not evidence
  that the old attachment-inclusive Enron archive is currently downloadable.
- [Govdocs1](https://digitalcorpora.org/corpora/file-corpora/files/): varied documents
  and smaller subsets; publisher explicitly warns of malware. Do not bulk-download
  into Dropbox or open in desktop document applications. Isolated selected-file
  evaluation requires a separate approved collection/execution boundary.
- [Faker](https://faker.readthedocs.io/en/master/) supplies fictional data components;
  it does not create coherent email threads or valid PDFs by itself.
- [Mailpit](https://mailpit.axllent.org/docs/) captures SMTP/MIME and exposes a test
  API, not a JMAP/IMAP/Gmail/Graph sync implementation or realistic-content feed.
  Keep optional relay/forward/link-check features disabled in offline tests.
- [Mailosaur](https://mailosaur.com/docs/email-testing/sending-from-mailosaur) is a
  commercial test service, including attachment-bearing mail to verified addresses.
  [Mockaroo](https://www.mockaroo.com/) is a data-generation service. Neither is
  required for local development, subscribed to, or approved for private data.

These are researched candidates, not installed dependencies or approved fixtures.

## Decision for the current build

Keep committed and CI fixtures synthetic under [AGENTS.md](../AGENTS.md). Use
independently written fictional messages to reproduce MIME structures and provider
response shapes. Do not quietly interpret "public" as permission to commit real
correspondence. Importing a selected public fixture needs an explicit owner-approved
policy/ADR update and the per-file review below. This document does not grant that
exception or authorize contacting the addresses or URLs in any sample.

The best next outside comparison is a small, reviewed MIME-parser regression set,
not a bulk corporate mailbox. Our ranking reflects relevance to attachment/parser
failures, not measured accuracy or a completed dependency audit.

## Verified primary-source shortlist

| Source | What was verified and why it may help | Adoption position |
|---|---|---|
| MimeKit | Its [test-data tree](https://github.com/jstedfast/MimeKit/tree/master/UnitTests/TestData) includes messages, mbox, encoders, HTML, images, TNEF, S/MIME and OpenPGP groups. The project [LICENSE](https://github.com/jstedfast/MimeKit/blob/master/LICENSE) is MIT. | First review candidate for MIME shape, transfer encoding and attachment accounting. Select files individually; repository licensing does not itself establish every embedded message/attachment's provenance or privacy clearance. Do not install a .NET runtime merely to copy examples. |
| Nodemailer MailParser | The [fixture directory](https://github.com/nodemailer/mailparser/tree/master/test/fixtures) lists mixed/nested MIME and decoder, delivery-status and resource-exhaustion regression files. [Package metadata](https://raw.githubusercontent.com/nodemailer/mailparser/master/package.json) and [documentation](https://nodemailer.com/extras/mailparser) declare MIT; retain and review the exact pinned [LICENSE file](https://github.com/nodemailer/mailparser/blob/master/LICENSE), not just that label. | First review candidate for streaming/decoding failure patterns. Prefer independently authored reproductions initially. Do not assume an issue-submitted message is fictional or covered for redistribution merely because the parser is OSS. |
| Apache James MIME4J | [Core test resources](https://github.com/apache/james-mime4j/tree/master/core/src/test/resources) include `testmsgs` and `mimetools-testmsgs`. The [LICENSE](https://github.com/apache/james-mime4j/blob/master/LICENSE) contains Apache-2.0 **and explicitly identifies Perl-MIME-Tools test messages under the Artistic License**; a [NOTICE](https://github.com/apache/james-mime4j/blob/master/NOTICE) is also present. | Strong parser-conformance reference, but do not label every fixture Apache-2.0. Resolve the selected file's origin and applicable notices before copying. Borrow test concepts now; a differential Java parser harness is a separate dependency decision. |
| CMU Enron | CMU describes its distributed corpus as roughly 0.5 million messages and explicitly says it **does not include attachments**. It documents redactions and asks users to respect participants' privacy. [Publisher page](https://www.cs.cmu.edu/~enron/). | Not the attachment acceptance corpus. Potential later search/threading evaluation only after permission/privacy review. Do not treat historical headers as authenticated sender truth or old business correspondence as a representative benchmark for current mail. |
| Apache SpamAssassin public corpus | Its [README](https://spamassassin.apache.org/old/publiccorpus/readme.html) prohibits sending the corpus into a live email system, says message-text copyright remains with original senders, and warns that external reputation results can change over time. The published set is historical. | Possible later offline spam/MIME comparison, never a live provider replay. No SMTP, replies, bounces, tracking-image requests, link fetches or DNS reputation queries. A corpus listing is not a modern phishing accuracy benchmark. |

CMU also links an EDRM attachment-inclusive Enron variant. That is a lead for a
later source investigation, **not a verified ready-to-use download**: this review
did not verify the current archive, availability, completeness, checksums, content
rights or security of that variant. Do not substitute an arbitrary mirror or an
old unverified attachment archive. [CMU's variant reference](https://www.cs.cmu.edu/~enron/).

## Raw MIME and provider protocol fixtures are different tests

An `.eml` file can test MIME normalization, multipart boundaries, attachment
receipts, character decoding and quarantine. It cannot prove account binding,
cursor advancement, token expiry, notifications, throttling or provider deletion
semantics. No public message is inherently a Gmail History, Graph delta or JMAP
transport test.

Keep separate, clearly labelled acceptance layers:

1. **Synthetic standards-shaped MIME:** independently authored RFC-style messages,
   multipart alternatives/mixed/related, inline resources, forwarded messages,
   encoded filenames, calendars, malformed encodings and bounded oversized cases.
2. **Synthetic provider envelopes:** fake HTTP/IMAP responses based on primary
   provider documentation, wrapping fictional evidence. Exercise Gmail history
   pagination; Graph account/folder-bound continuation and folder removal; JMAP
   baseline/query-state differences; IMAP UIDVALIDITY and exact fetched bytes.
3. **Reviewed outside parser fixtures:** only after approval; compare parser
   interpretations with explicit expected outcomes. An upstream parser result is
   a useful comparison, not the sole security oracle.
4. **Disposable-account live acceptance:** separately authorized accounts/folders
   using newly generated synthetic messages; never replay public correspondence.

Relevant implemented contracts: [provider connectors](EMAIL_PROVIDER_CONNECTORS.md),
[Gmail](GMAIL_READ_CONTRACT.md), [Graph](GRAPH_READ_CONTRACT.md),
[IMAP](IMAP_READ_CONTRACT.md), and [test/evaluation gates](TESTING_AND_EVALS.md).

## Gate for any future selected-file adoption

Each gate is required; an unresolved item means no ingestion or redistribution.

- **Authority and purpose:** identify the exact regression/evaluation gap, dataset
  reviewer, owner approval and applicable policy exception. Distinguish local
  inspection permission from redistribution in Git, CI artifacts or a release ZIP.
- **Provenance:** record official upstream URL, repository and exact commit SHA,
  original path, retrieval date, byte size and SHA-256 of each source file. For an
  archive, record both container and selected-member hashes. Branch names, current
  URLs, filenames and historical MD5 alone are not sufficient pins.
- **Rights:** review LICENSE, NOTICE, directory/per-file notices, contribution
  provenance and embedded attachment rights at that pin. Resolve conflicting or
  missing terms with the owner before copying. Retain required notices. Changing
  names or sanitizing a message does not itself settle copying rights.
- **Privacy/content:** review bodies, quoted history, headers, addresses, IDs,
  signatures, URLs, secrets and every selected attachment. Do not expose originals
  in logs, screenshots, issues or model prompts. Public availability is not consent
  for unrelated processing. Prefer a minimal independently generated reproducer
  when actual correspondence adds no necessary regression coverage.
- **Collection boundary:** use a separate one-shot, allowlisted fetch stage without
  mailbox/model credentials, capped downloads and reviewed redirects. Parsing and
  tests then run offline. No automatic "latest corpus" download during ordinary CI.
  Archive handling must reject traversal, absolute paths, links, special files,
  excessive members and decompression bombs before any extraction.
- **Execution boundary:** disable network, SMTP and mailbox executors; do not render
  active HTML, open office applications, run macros, follow calendar URLs or process
  embedded executable code. Use bounded isolated parsers, explicit unsupported
  outcomes and process memory/time limits. Scanning is not proof that a file is safe.
- **Oracle and accounting:** record expected body/attachment counts, hashes,
  encoding, parser outcome, quarantine/deferred reason and relevant provider
  envelope separately. Every input needs a receipt; an unsupported file is not
  silently counted as successfully parsed. Preserve source and transformed hashes
  separately if an approved transformation is made.
- **Reporting and lifecycle:** publish fixture IDs, bounded counts, outcomes and
  timings, not private excerpts. Record fixture manifest and parser versions.
  Define access, retention and deletion for external originals and generated
  artifacts; exclude them from source ZIPs until redistribution is approved.

No individual upstream fixture has passed this gate yet. Current synthetic tests
and mock-provider results remain exactly that; this research does not establish
real-provider or public-corpus compatibility, attachment extraction completeness,
or production readiness.
