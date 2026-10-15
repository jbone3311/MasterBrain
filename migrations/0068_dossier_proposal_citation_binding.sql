BEGIN;

-- ADR-205: retain exact cited bases for new imported proposals. Historical
-- ADR-186/202 rows stay readable with NULL fields and their original rules.
ALTER TABLE public.knowledge_proposals
    ADD COLUMN import_quote_evidence_id text
        CHECK (import_quote_evidence_id IS NULL
               OR import_quote_evidence_id ~ '^evidence_[a-f0-9]{32}$'),
    ADD COLUMN import_entity_citation_id text
        CHECK (import_entity_citation_id IS NULL
               OR import_entity_citation_id ~ '^evidence_[a-f0-9]{32}$'),
    ADD CONSTRAINT imported_member_entity_citation_only CHECK (
        import_entity_citation_id IS NULL OR payload->>'kind'='member'
    );

ALTER TABLE public.knowledge_proposals
    ADD CONSTRAINT knowledge_proposal_import_quote_evidence_fk
        FOREIGN KEY (tenant_id,import_quote_evidence_id)
        REFERENCES public.brain_evidence(tenant_id,id),
    ADD CONSTRAINT knowledge_proposal_import_entity_evidence_fk
        FOREIGN KEY (tenant_id,import_entity_citation_id)
        REFERENCES public.brain_evidence(tenant_id,id);

COMMIT;
