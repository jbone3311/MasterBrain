# ADR-167: Fail closed on unencodable FileOS names

Status: accepted for synthetic v1 intake and the nonpublishing donor shadow.

## Context

Linux filesystems may contain names with byte sequences that Python represents
through surrogate escapes. Those names cannot be encoded as UTF-8 for stable
DataCore IDs or PostgreSQL text. The pinned FOS-Master scanner can walk and
hash such a file, but its SQLite text insert is not a portable acceptance
path. This Mac's filesystem refuses to create the fixture, so a local pass
cannot establish Linux behavior.

## Decision

- Before path classification, metadata inspection or byte reads, v1 snapshot
  and the nonpublishing donor-policy shadow reject an unencodable directory or
  file name. They do not descend into that directory or read that file.
- Each affected *encodable parent directory* receives one
  `invalid_locator_encoding` coverage error. The invalid bytes and any
  surrogate-containing path are absent from manifests, API output and logs.
  Other valid siblings remain visible, but a v1 completion is refused; a
  partial scan cannot infer absence or freshness.
- The shadow remains nonpublishing. Its transition-candidate builder refuses
  this error before staging or approval, with a content-free operator message.
  The existing relational error-code allowlist is deliberately not widened;
  there is no v2 baseline, activation, FileOS cutover or FOS-Master change.
- This is an intentional safety divergence, **not** donor-output parity. The
  owner must resolve such a name or approve a separately designed reversible
  representation policy before a live cohort can transition.

## Verification and rollback

Unit tests inject surrogate names and prove no invalid target inspection,
one parent error, valid-sibling retention, completion refusal and candidate
refusal. A Linux-required test creates actual invalid-byte names, runs the
exact pinned donor source in an in-memory SQLite database, and compares the
shared snapshot and shadow outcomes. It must fail rather than skip on the
hosted Linux gate. The donor checkout and test-only source snapshot are not
modified. Rollback removes the new scan guard only after a reviewed alternative
prevents unencodable locators from entering IDs or storage; do not treat a
rollback as authorization to publish an incomplete run.
