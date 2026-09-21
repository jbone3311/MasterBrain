# Owner email reader

Implemented under [ADR-045](adr/045_owner_message_reader.md). Exact verification
belongs in [BUILD_RECEIPT.md](BUILD_RECEIPT.md). This feature does not finish the
hosted/live-mail product. Start the owner test with [USER_TESTING.md](USER_TESTING.md).

## What you can read

Select **Read email** on a search result. For original MIME up to 1 MiB, the reader
decodes the complete selected body, including quoted replies, independently of the
4,000-character evidence excerpt and 100,000-character search projection. Plain
text is preferred over its HTML alternative. HTML-only mail is converted to inert
text: no formatted HTML, links, tracking images, scripts or embedded previews run.
Character decoding can replace invalid bytes; normalized whitespace/NUL handling
means this is not byte-for-byte source display. Download the original for exact bytes.

Header display is independently bounded: 100 headers, 4,000 characters per value,
65,536 value characters total. Displayed sender is not proof of authenticated
identity; ambiguous senders remain visible through the header view.

For retained MIME larger than 1 MiB, the screen clearly says **stored text
projection**, with truncation status. It does not launch the isolated worker or
raise the API's parsing budget. Such a message needs prior successful authorized
processing to have a searchable evidence version. Still-held mail is not silently
made readable by this route. Large-body on-screen reading remains future work.

## Original and attachment downloads

Check the unscanned-files acknowledgement, then explicitly choose a download.
The original `.eml` preserves all retained bytes (up to the configured 16 MiB
external-storage limit), including headers, alternative bodies and MIME attachments.
Originals beyond ingestion/storage limits have not been imported.

Individual leaf parts are available for small source MIME. They are bound to the
exact immutable receipt path/size/hash. Nested message/container parts and large
MIME require the original export; no archive is unpacked. Attachments save with
a generated `.bin` name; the original safe filename is displayed in the reader.
Renaming or opening a file is the user's responsibility. **Unscanned is not safe.**
These downloads do not start PDF extraction, install software or open the files.

The browser validates identity, length, response type/disposition and SHA-256
before offering an explicit **Save verified file** link. Saving requires that
second user click, not an automatic action after a network request. At most one
prepared file is retained per view; a new export, closing/resetting the reader or
unchecking consent revokes its temporary blob URL. The browser can block saving;
“save requested” is not proof of a completed save.

## HTTP contract

All routes require current owner membership, active source account, human client
kind and `email.evidence.read`. No client-provided tenant, path, URL, raw hash or
storage reference can select content. Historical immutable versions remain readable
even if provider state later changes/deletes the current message; this is retained
evidence, not a claim that it still exists at the provider.

| Route | Result |
|---|---|
| `GET /v1/reader/{evidence_uuid}` | Complete selected small-message body or explicit large projection, bounded headers, receipt inventory |
| `POST /v1/reader/{evidence_uuid}/original` | Exact retained MIME as octet-stream attachment |
| `POST /v1/reader/{evidence_uuid}/attachments/{receipt_uuid}` | Verified decoded leaf bytes as octet-stream attachment |

Both POSTs require exactly `{"acknowledge_unscanned": true}`. Coerced booleans,
false/missing consent and unknown fields are rejected. Scope/kind denial is 403;
unknown/foreign evidence or inactive source account is 404; unsupported separate
export is 409; unavailable/corrupt storage or reader failure is scrubbed 503.
Cookie requests retain the existing Origin/CSRF requirements, but the current
owner UI uses explicit bearer mode; browser-login UI is not added here.

Downloads use `application/octet-stream`, generated ASCII disposition names,
`no-store`, `nosniff`, no-referrer, sandbox CSP and `X-Content-SHA256`.
No general raw-object or MCP download tool exists. Assistant evidence stays bounded.

## Audit, recovery and rollback

Current identity/owner/account authority is rechecked after loading/parsing source.
`message.read`, `message.original_export`, `message.attachment_export` record
identifiers, not content. An exported copy cannot be revoked retroactively.
Hash mismatch, missing encrypted objects/keys, or access loss returns no bytes.
Do not bypass verification, regenerate originals from projections, or log bodies
to troubleshoot. Follow [storage recovery](OPERATIONS_RUNBOOK.md#encrypted-evidence-failures).

No migration/dependency/parser-version change. To roll back, revert routes and
reader UI together; retain database, raw objects and immutable snapshots. This
does not alter provider cursors, rules, approval jobs or mailbox permissions.
