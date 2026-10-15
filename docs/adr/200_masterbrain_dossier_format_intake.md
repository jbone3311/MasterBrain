# ADR-200 — Bounded intake of MasterBrain dossier Markdown

Status: accepted for synthetic-only, read-only implementation. This does not
authorize a live source, a KnowledgeCore write, or a FileOS cutover.

## Context

The owner selected MasterBrain's existing ADR-197 project dossier export as
the Librarian exchange format. That export is a human-readable, bounded view
of currently authorized reviewed rows. It includes claimed object and evidence
IDs and short escaped quote previews. It does **not** include each assertion's
full original quote, observed time, all evidence links, reviewer, or a signed
manifest. Its cutoff is a read boundary, not an observation time. Treating it
as a complete publication payload would invent provenance.

## Decision

1. Introduce a pure, model-free, read-only parser for the current fixed
   ADR-197 Markdown layout. Accept at most 64 KiB UTF-8, the exact header,
   metadata shape, section order, one project row, at most 25 rows per other
   section, bounded IDs and syntactically shaped citations. Reject extra
   headings, lines, sections and malformed metadata. No filesystem or network
   read is part of this parser.
2. Return an **untrusted candidate inventory**, not `KnowledgeAssertion`
   objects or an ADR-186 proposal batch. All parsed IDs and citations are
   claims from the input, never evidence checks. Preserve each inert source
   line for a human preview; mark every row `proposal_ready=false` and state
   why. Never interpret an exported `reviewed` label as approval to republish.
3. A later separately gated stage operation must retrieve current authorized
   evidence, verify full quotes and all direct links, obtain missing typed
   metadata and explicit human review, then use the private proposal queue.
   Unsupported inferred rows and changed/hidden evidence fail closed. A
   separate manifest/sidecar may be designed if full-fidelity round trips are
   needed; this parser does not silently manufacture one.

## Acceptance and rollback

Use fictional export-shaped dossiers only. Prove deterministic inventory for
all six sections, empty sections, repeated IDs, size/row caps, malformed
citations and injected headings, non-UTF-8/surrogate denial, and no proposal or
reviewed write. Run the repository gates. Rollback removes only the pure parser;
the export, proposal queue and reviewed Knowledge data remain unchanged.
