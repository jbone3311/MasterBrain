# ADR-216 — Preserve FOS fact-verifier behavior without promoting it to truth

Status: isolated parity tranche implemented for fictional local testing on an
open PR; no production attestation or financial claim publication is enabled.

## Context

FOS-Master's pinned `_SYSTEM/tools/fact_verify.py` classifies source tiers by
filename/type/sender, searches extracted text for a value or numeric variants,
and stores a source hash with a `CONFIRMED`, `DISPUTED` or `UNVERIFIED` result.
Its source SHA-256 is recorded in `FOS_TOOL_INVENTORY.md`. This useful donor
behavior is not yet a safe cross-source MasterBrain evidence policy.

The donor has deliberate and accidental limits: one matching source suffices
for `CONFIRMED` even when another has no readable text or a cited ID is
missing; any readable mismatch wins `DISPUTED`; numeric matching is a raw
substring search (`25` can match `125`); sender-domain matching is unanchored
(a lookalike domain can receive T2); stored hashes can be reused without
rechecking the file at confirmation time; float formatting is not exact money
parsing, and `Infinity` raises. A filename or sender is not proof of document
authority or independent corroboration. An old donor confirmation is not a
current-source check after source mutation, exclusion or grant change.

## Decision

Copy only the pure classifier and numeric-variant functions into an isolated
DataCore compatibility module and encode the donor status precedence there.
The original FOS-Master checkout and its database remain untouched. Tests load
the exact-hash donor functions into a sandboxed namespace, compare nine source
shapes and 500 seeded numeric cases, and execute the donor's original
`confirm` against a disposable fictional SQLite database. The tests explicitly
retain misleading-but-real donor outcomes so migration cannot silently change
behavior. This module is *not* called by Brain API, KnowledgeCore publication,
source ingestion, or financial reports.

MasterBrain's eventual source-tier attestation must instead bind an authorized
reviewer, a specific immutable source version and verified content hash, a
controlled document type/issuer or authority, the extraction method and
coverage, observed time, and current grant/exclusion state. Text occurrence,
source independence, and ownership are separate checks. Unreadable, missing,
stale, or ambiguous evidence must stay unknown; a source-type heuristic can
only propose a tier. A financial claim requires explicit owner review and
publication under a separate ADR and never derives a balance from generic
money-fact sums.

## Acceptance and next gate

The parity suite must pass against the pinned donor and fail on hash drift;
malformed and missing-source cases must be visible. Ruff and type checking
must pass. Next: design the immutable tier-attestation schema and restricted
review operation, then add synthetic current-version/hash/grant/OCR-failure
cases before connecting any tier to a project dossier. Independent restore,
hosted CI and merged-main gates remain outstanding. No live data is in scope.
