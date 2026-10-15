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

-- The importer never creates a context-bound row without its cited bases.
-- Enforce this for direct SQL too, without rewriting historical ADR-202 rows.
CREATE FUNCTION public.guard_new_dossier_proposal_citations() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
DECLARE context_digest text;
BEGIN
    SELECT b.import_context_sha256 INTO context_digest
    FROM public.knowledge_proposal_batches AS b
    WHERE b.tenant_id=NEW.tenant_id AND b.id=NEW.batch_id;
    IF context_digest IS NULL THEN
        IF NEW.import_quote_evidence_id IS NOT NULL
           OR NEW.import_entity_citation_id IS NOT NULL THEN
            RAISE EXCEPTION 'unexpected imported proposal citation';
        END IF;
    ELSE
        IF NEW.import_quote_evidence_id IS NULL
           OR NOT EXISTS (
               SELECT 1 FROM jsonb_array_elements_text(NEW.payload->'evidence_ids') AS e(id)
               WHERE e.id=NEW.import_quote_evidence_id
           ) THEN
            RAISE EXCEPTION 'missing imported proposal quote citation';
        END IF;
        IF NEW.payload->>'kind'='member' AND NEW.import_entity_citation_id IS NULL THEN
            RAISE EXCEPTION 'missing imported member entity citation';
        END IF;
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER new_dossier_proposal_citations
    BEFORE INSERT ON public.knowledge_proposals
    FOR EACH ROW EXECUTE FUNCTION public.guard_new_dossier_proposal_citations();

COMMIT;
