# ADR-156 — Do not inspect symlink targets during FileOS donor shadow enumeration

Status: accepted for the synthetic, nonpublishing donor-policy shadow only.

## Context

ADR-152 confines directory listing and file reads, but deliberately retained
`DirEntry.is_dir()` with its default follow-symlinks behavior to distinguish
directory links from file links. For a link under an authorized root, that call
can inspect the target's type outside the root. The target is not listed or
read, yet this is still an unnecessary cross-boundary metadata observation
before any live-root shadow can be considered.

## Decision

- Classify a directory entry as a symlink first, without following it. Record
  every symlink, whether its target is a file, directory, missing or changing,
  as a `symlink_skipped` coverage error. Do not classify a symlink's target as
  a donor directory or file and do not traverse or hash it.
- Use no-follow directory classification for non-symlink entries. Preserve
  ordinary file and directory order, donor junk classification, bounded row
  counts, descriptor-confined traversal and the `publishable: false` shape.
- This deliberately changes the shadow result for a stable directory symlink
  from an exclusion to an error. A transition candidate containing one now
  fails closed rather than treating that locator as safely excluded. It does
  not change FOS-Master, the publishable v1 scanner or any existing database
  state. The shadow profile and candidate versions advance to v2. Existing v1
  packets remain immutable historical evidence but cannot be newly staged or
  sealed under the new target-type policy; an operator must run a new scan and
  review rather than reinterpret an old packet. No automatic approval, v2
  activation, source effect or cutover follows.

## Verification and rollback

Test file, directory, dangling and outside-root symlinks; use a fake directory
entry that refuses target-following classification to prove the scanner never
asks for it. Re-run ordinary pinned-donor golden parity, metadata-only and
3,000-file stress/fault tests, plus CI, strict runtime and populated restore.
For rollback, stop unpublished transition attempts that depend on this error
classification, restore the earlier shadow scanner and review any packet
created under this profile. Do not rewrite retained packets or donor state.
