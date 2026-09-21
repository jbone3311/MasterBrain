# ADR-045 — Owner message reader and explicit evidence downloads

Accepted for the local prototype, 2026-09-21, following the owner's request to
finish reading retained email and test it. This is not public-hosting approval.

## Decision

Add a human-owner-only reader, separate from bounded assistant evidence. Resolve
an immutable evidence UUID under current tenant/owner/account authority, verify
the retained source's length/hash, and recheck authority before returning content.
No request accepts storage paths, SQL, provider IDs, URLs, or object keys. Existing
`email.evidence.read` scope is required; assistant and worker identities cannot
use the reader or download routes. MCP retains excerpt-only access.

For source MIME within the existing 1 MiB in-process parser budget, display the
complete selected body (plain preferred, HTML converted to inert text), bounded
header metadata and attachment receipt inventory. Do not impose the search
projection's 100,000-character cutoff on this body. Never render email HTML,
auto-link URLs, load images, execute files or recursively unpack nested messages.

For larger originals (up to the existing encrypted-storage 16 MiB bound), display
the stored body projection with explicit provenance/completeness, not an implied
full parse. The complete original remains downloadable. A large-message on-screen
reader and per-part export need a separate restricted worker contract; this change
does not move that parsing into the API. Malformed sources fail closed.

An explicit POST with a closed `acknowledge_unscanned: true` body can download the
hash-verified original, or a receipt-bound leaf attachment from small MIME. Verify
the attachment's path, size and decoded hash against its immutable receipt. Nested
containers require the original export; no archive extraction. Responses use
octet-stream, attachment disposition, generated ASCII names, no-store, nosniff and
sandbox CSP. Attachments are saved with a `.bin` suffix, not an executable/HTML
filename from mail. Explain that files are unscanned and must not be opened blindly.
Downloads authorize no mailbox write and contain no provider credentials.

Read/download audit events contain identifiers only. A completed server response
is not proof the browser saved a file. Current access can be revoked between any
two requests; checks do not retroactively erase a previously delivered download.

## UI and verification

The owner selects “Read email” from search. Session, query, account and reader
generations fence late responses and detached callbacks. Clear private text on
credential changes/denial and release temporary download URLs. No browser storage,
automatic download, HTML renderer or external script. Provide synthetic long-body,
HTML, Unicode and attachment examples for user acceptance.

Unit tests cover MIME/header/text/part boundaries, API tests cover scopes/kinds,
validation and safe response headers; PostgreSQL tests cover tenant/account/source
binding, immutable history, encrypted storage, audit and revocation. Node tests
cover safe text, stale requests and explicit downloads. Run existing regression,
lint/type, documentation, container and restore gates; report unrun levels honestly.

## Rollback and migration

No schema, parser-provenance, dependency, mailbox permission or stored-evidence
change. Disable/revert the new routes/UI together; original bytes and snapshots
remain untouched. Historical citations remain readable. Hosted storage, malware
scanning, actual provider acceptance and production identity remain separate gates.
