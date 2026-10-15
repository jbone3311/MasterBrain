# ADR-194 — Bounded reviewed artifact section in project dossiers

Status: accepted for synthetic/disposable implementation only. This is a
read-only extension of ADR-162/163/193, not a complete Librarian export or a
FileOS cutover.

## Context

The exact-project dossier returns reviewed events, commitments and roles.
ADR-193 separately records reviewed links to exact Email/FileOS evidence
occurrences. A reader currently needs a second request to discover those
links, and the owner workspace cannot show them beside the other reviewed
project context. A matching filename or hash cannot substitute for a reviewed
association.

## Decision

- Add `artifact_limit` (1–25, default 10) to the existing dossier request and
  return an independently bounded `artifacts` list plus
  `artifacts_truncated`. Each row contains the reviewed link ID, exact
  artifact and quoted-basis evidence IDs, source kind, relation, assertion
  status, observation and recording time. No quote, path, extracted text or
  bytes appear. The dossier's recorded-time cutoff applies to these rows.
- In the same tenant-bound dossier transaction, filter the project and both
  evidence occurrences by current active source, source grant, Email
  exclusion and exact basis-quote presence before sorting and limiting. Reuse
  ADR-193's visibility predicate so the separate link-history API and dossier
  cannot disagree about which rows are currently disclosable. A hidden link
  cannot consume a page slot or cause a truncation signal.
- The existing `visibility` switch still applies to events, commitments and
  roles. Artifact links have no correction-chain/current-roster semantics;
  the response labels this fourth section `retained_reviewed_link_history`
  regardless of that switch. A `retracted` row does not automatically negate
  another row. A recorded cutoff is not a durable snapshot or source-freshness
  proof. Evidence expansion keeps its separate permission.
- The provider-neutral client and first-party workspace validate the complete
  bounded response, render the links as inert text, and offer separately
  authorized evidence drill-down. The workspace continues to request the
  dossier only on an explicit project action and uses a fixed five-row limit.
  It does not auto-open files or change any source.

## Verification and rollback

Use fictional Email and FileOS evidence in disposable PostgreSQL. Test
source-grant/exclusion/stale-version filtering before limit, independent
truncation, cutoff, tenant denial, malformed response rejection, hostile text
inertness, and no automatic browser request. Run the repository and hosted
gates before merge. Rollback removes the extra dossier fields/client/browser
section while retaining ADR-193's immutable links and separate API. No schema
migration, live source access or FOS-Master modification is required.
