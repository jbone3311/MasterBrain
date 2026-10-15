BEGIN;

-- ADR-202: optional immutable context digest for imported Markdown batches.
-- Historical and generic ADR-186 batches retain NULL and their original digest.
ALTER TABLE public.knowledge_proposal_batches
    ADD COLUMN import_context_sha256 text
    CHECK (import_context_sha256 IS NULL OR import_context_sha256 ~ '^[a-f0-9]{64}$');

COMMIT;
