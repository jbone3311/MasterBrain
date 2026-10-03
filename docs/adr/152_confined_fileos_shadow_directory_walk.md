# ADR-152 — Confine the donor-policy shadow directory walk

Status: accepted for the synthetic, nonpublishing shadow path only.

## Context

ADR-111's shadow inventory uses `os.walk` to enumerate directories, while
ADR-100/111 confine individual file reads. If a descendant directory becomes
an outside-root symlink between `os.walk`'s parent and child iterations, the
walker can enumerate outside filenames before the confined leaf reader refuses
them. A junk filename can enter the returned exclusion ledger without any
file-byte read. Root identity checks do not cover this ancestor swap.

## Decision

- Enumerate every directory through a descriptor opened from the authorized
  root and each ancestor with `O_DIRECTORY | O_NOFOLLOW`. Never use `os.walk`
  or follow a descendant symlink to list children. Bind the root descriptor
  to the initial device/inode observation.
- Reopen a child locator before its turn. If it has disappeared, become a link,
  or cannot be opened, record a bounded directory coverage error; do not
  enumerate it or publish a successful row. Preserve ordinary donor membership,
  ordering, file hash/metadata handling and the existing nonpublishable shape.
- Keep the existing v1 snapshot, database state, source permissions, and
  FOS-Master checkout unchanged. This does not decide donor policy, real cloud
  placeholder handling, v2 current visibility or FileOS cutover.

## Verification and rollback

Use synthetic roots to test a descendant symlink swap before opening a child,
an ancestor swap during a nested scan, root replacement, unreadable directory,
symlink leaves, ordinary pinned-donor parity, record limits and metadata-only
no-byte-read behavior. Run focused tests, 3,000-file pinned-donor comparison,
full CI, strict runtime, restore and documentation gates. A rollback restores
the prior shadow implementation only after stopping transition attempts that
depend on it; no persisted evidence or donor state is rewritten.
