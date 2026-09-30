# ADR-111 — Nonpublishing FileOS donor-policy inventory shadow

Status: proposed; isolated DC-002G implementation pending review.

## Context

The current publishable FileOS snapshot uses the generic DataCore dedupe policy,
which differs from the pinned FOS-Master scanner's junk/operational path policy and
100 MiB versus 2 GiB hash boundary. The copied donor classifier has pure-function
parity, but no scanner consumes it. Silently replacing snapshot policy v1 would
break its completion-policy identity and could infer false absences.

## Decision

- Add a separate, explicitly named read-only shadow inventory. It is not a
  `snapshot_tree` manifest and cannot be submitted to DataCore intake, publication,
  completion, search or the FileOS operator. No default or CLI behavior changes.
- Apply the pinned donor's junk-file, junk-directory and operational-directory
  membership classifier. Keep otherwise valid dot-directories and `.db` files.
- Hash ordinary regular files at or below the donor's 2 GiB cap using DataCore's
  confined, bounded, no-follow reader. Mark larger files metadata-only without
  reading them. An explicit metadata-only scan also reads no file content. A
  simulated dataless flag is recorded as metadata-only without materializing it.
- Refuse symlinks and uncertain reads as reason-coded shadow gaps. This is an
  intentional safety difference from FOS-Master, which follows file symlinks.
  Never interpret a shadow gap or missing row as deletion evidence.
- Return only normalized path, size, SHA-256 or null, state, exclusion and error
  records for synthetic comparison. The shadow object contains no source item IDs,
  completion marker or publishable manifest version.

The exact donor commit and source hashes remain pinned in
[the inventory shadow contract](../FILEOS_INVENTORY_SHADOW.md). This tranche does not
authorize live-cloud scanning, a publishable v2 policy, a 2 GiB production read
budget, legacy policy transition, FileOS cutover or a donor edit. A later ADR must
define those contracts and obtain owner approval before switching an integrated
path.

## Verification

Use a fictional temporary tree and the pinned donor scanner in isolated in-memory
SQLite. Compare membership, size and SHA-256 for ordinary files; require zero
unexplained differences. Exercise donor junk/operational exclusions, hidden content,
`.db` content, replay and changed files, metadata-only mode, 100 MiB + 1 and 2 GiB
+ 1 sparse boundaries, simulated dataless files, symlinks, source races and unreadable
coverage. Assert the existing snapshot v1 and its completion policy remain unchanged.
Hosted CI without the donor checkout may run synthetic unit tests, but cannot claim
the live pinned-donor gate.

## Rollback

Remove the standalone shadow module and comparator additions. No database rows,
source files or existing snapshot behavior need restoration.
