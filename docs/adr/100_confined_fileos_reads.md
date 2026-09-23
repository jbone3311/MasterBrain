# ADR-100 — Confine FileOS snapshot and extraction reads to the authorized root

Status: accepted for isolated implementation; hosted gate and restore passed on
code head `6e2eb8e` in PR #25, including the ancestor-above-root guard. No
production cutover.

## Context

The default FileOS snapshot checks a path and then calls a pathname-based hash
reader. Text and PDF/Office extraction likewise resolve/check a path before a
separate pathname open. A file or ancestor directory can be replaced with a
symlink between those operations. Hashing or extraction could then read bytes
outside the authorized root, despite later size/hash comparison. A mismatch is
not an adequate confidentiality control: outside bytes have already been read.
The pinned FOS-Master scanner follows file symlinks, including outside-root ones;
that observed donor behavior is intentionally not adopted by MasterBrain.

## Decision

- Use one DataCore root-confined, descriptor-relative read primitive for FileOS
  snapshot hashing and text/PDF/Office extraction. Open the resolved authorized
  root and every ancestor from the filesystem root with
  `O_DIRECTORY | O_NOFOLLOW`; open the leaf with
  `O_NOFOLLOW | O_NONBLOCK`, require a regular file, and read only a bounded number
  of bytes. Never use a prechecked pathname as the byte source.
- Compare file identity and size/time metadata on the open descriptor before and
  after reading, then reopen the locator through the same confined walk and
  compare identities. A move, replacement, growth or read fault fails closed.
- Preserve the existing snapshot/output identities and normal read results. A
  direct symlink remains skipped under the default no-follow policy. The explicit
  read-only internal-file-symlink option may resolve a target, but bytes are read
  only by reopening that target through the confined root, with link stability
  checked afterward. Outside-root links remain errors. Publication still does not
  gain symlink extraction authority.
- Unsupported platforms without the required descriptor flags fail closed rather
  than falling back to path-based opens. Keep the donor hash/dedupe helper unchanged
  to preserve DC-001 parity; the FileOS source adapter uses the safe primitive.
- This is not donor inventory-policy adoption, a new permission, a file effect, a
  production cutover or a FOS-Master edit. No applied migration changes.

## Verification

Use synthetic roots only. Test ordinary nested files, zero and bounded sizes,
direct/internal/outside symlinks, file and ancestor swaps both below and above
the authorized root immediately before open,
read-time mutation, source removal/replacement, and exact extraction outcomes.
Run the pinned donor shadow to confirm that ordinary common SHA/size parity remains
while explicit symlink differences remain reason-coded. Run full hosted CI,
restricted workers, populated restore and documentation inventory on the exact PR
head. A local test without a disposable database is not SQL verification.

## Rollback and limits

Stop FileOS publication if the safe reader fails in an environment; keep prior
evidence, completion receipts and active index generations. Roll forward with a
corrected reader or restore through the tested procedure. Never disable the
confinement check or silently retry with a pathname read. This does not attest to
the trustworthiness of the scanner, stop a malicious process with direct database
authority, or prove live cloud-placeholder behavior. FileOS cutover remains gated.
