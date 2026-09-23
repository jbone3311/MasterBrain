# ADR-098 — Bind FileOS intake and completion to one physical root

Status: implemented in isolated PR #22; runtime head passed hosted CI and populated
restore; review and integration pending.

## Context

The private FileOS publisher resolves a configured root and verifies individual
source files, but the snapshot and database do not retain an identity for that root.
The same `source_id` could therefore be reused with a different empty or similarly
shaped directory. Intake could change current item pointers before the completed-run
policy, exclusion and mass-loss guards discover a problem. Absence inferred between
different roots is not trustworthy.

## Decision

- The scanner computes `fileos-root-binding-v1` from the resolved root's exact
  filesystem-encoded absolute path plus device and inode numbers. It records only
  a lowercase SHA-256 and version in the manifest, not the path. Recheck the root
  identity after walking; a change makes the snapshot incomplete. Symlink aliases
  resolving to the same directory share the binding; a changed path or replaced
  directory does not. This is an accidental-drift fence, not a cryptographic
  attestation against a malicious scanner or inode reuse.
- The private controller verifies the manifest binding against its configured
  root before database setup or check-mode success. The library adapter checks
  before intake and after extraction, before a completed-run receipt can record
  absence. Neither check opens excluded file content.
- Migration 0032 adds a nullable historical root digest to `brain_sources` and
  immutable FileOS completion receipts. A source trigger requires a digest for new
  FileOS sources, preserves old NULL rows, and prevents a bound source from changing
  digest or kind while allowing status changes. A receipt `NOT VALID` check preserves
  old NULL rows but requires a valid digest on new receipt inserts.
- The first new intake binds a new FileOS source or an existing empty legacy source.
  Under its source row lock,
  every later intake requires the same digest, including partial imports. An older
  unbound source with items or completed receipts cannot be silently claimed by a
  new root. Completion independently compares its digest with the source and prior
  completed receipt under the existing source lock. Unknown or changed historical
  root identity refuses completion before any new receipt or absence event commits.
- No force flag, automatic legacy rebaseline, donor policy switch, FOS-Master edit,
  source effect or cutover is authorized. A reviewed transition must preserve
  evidence, decide current-search visibility and demonstrate rollback.

The fingerprint can be guessed from known paths and filesystem identifiers; keep it
inside the existing private manifest/database boundary and never expose it through
Brain API output or content-bearing logs. A remote/cloud FileOS adapter will need a
different versioned provider-native root identity and separate acceptance decision.

## Verification

Use fictional temporary roots for stable replay, symlink alias, root path change,
same-path inode replacement, malformed/missing digest and scan-time root drift.
PostgreSQL tests prove pre-intake refusal of root drift and preservation of the
previous completion; populated migration tests preserve unknown legacy roots,
refuse a silent populated-source claim, and enforce new-insert constraints.
Hosted CI 35890079983 passed 2,721 Python tests with nine expected skips, plus
type, browser, deployment, documentation and restricted-worker gates. Populated
restore 35890079939 passed. These synthetic gates do not establish live-source
parity or authorize cutover. FOS-Master remains pinned and unchanged.

## Rollback

Stop FileOS intake/completion before deploying older code that cannot provide or
verify the root digest. The migration does not rewrite historical rows. Roll forward
with corrected code or restore from the tested backup workflow; do not clear a
binding, backfill unknown roots, or down-migrate retained evidence automatically.
