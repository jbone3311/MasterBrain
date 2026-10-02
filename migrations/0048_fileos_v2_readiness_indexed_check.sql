BEGIN;

-- Forward-only indexed replacement of the v2 readiness closure query from 0047.
CREATE OR REPLACE FUNCTION public.enforce_index_generation_ready() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
DECLARE expected_items integer;
DECLARE expected_documents integer;
DECLARE expected_chunks integer;
DECLARE actual_items integer;
DECLARE actual_documents integer;
DECLARE actual_chunks integer;
DECLARE documents_without_chunks integer;
DECLARE chunk_documents integer;
DECLARE basis text;
DECLARE attempt uuid;
DECLARE attempt_membership jsonb;
DECLARE generation_membership jsonb;
DECLARE unmatched_chunks integer;
DECLARE base_chunks integer;
BEGIN
    SELECT item_count,document_count,chunk_count,basis_kind,v2_attempt_id
    INTO expected_items,expected_documents,expected_chunks,basis,attempt
    FROM public.brain_index_generations
    WHERE tenant_id=NEW.tenant_id AND id=NEW.generation_id AND source_id=NEW.source_id;
    SELECT count(*)::integer,count(document_id)::integer
    INTO actual_items,actual_documents
    FROM public.brain_index_generation_items
    WHERE tenant_id=NEW.tenant_id AND generation_id=NEW.generation_id;
    SELECT count(*)::integer INTO actual_chunks
    FROM public.brain_index_generation_chunks
    WHERE tenant_id=NEW.tenant_id AND generation_id=NEW.generation_id;
    IF basis='v2' THEN
        -- The item table admits each document once and the chunk FK admits
        -- only those documents. A set count proves coverage without 3,000
        -- repeated anti-joins through forced RLS.
        SELECT count(DISTINCT document_id)::integer INTO chunk_documents
        FROM public.brain_index_generation_chunks
        WHERE tenant_id=NEW.tenant_id AND generation_id=NEW.generation_id;
        documents_without_chunks := actual_documents - chunk_documents;
    ELSE
        SELECT count(*)::integer INTO documents_without_chunks
        FROM public.brain_index_generation_items i
        WHERE i.tenant_id=NEW.tenant_id AND i.generation_id=NEW.generation_id
          AND i.document_id IS NOT NULL AND NOT EXISTS (
              SELECT 1 FROM public.brain_index_generation_chunks c
              WHERE c.tenant_id=i.tenant_id AND c.generation_id=i.generation_id
                AND c.document_id=i.document_id
          );
    END IF;
    IF expected_items IS NULL OR actual_items<>expected_items
       OR actual_documents<>expected_documents OR actual_chunks<>expected_chunks
       OR documents_without_chunks<>0 THEN
        RAISE EXCEPTION 'index generation is not complete';
    END IF;
    IF basis='v2' THEN
        -- Two ordered exact ledgers avoid a row-by-row join through forced
        -- tenant RLS. JSONB equality compares every field, not a digest.
        SELECT COALESCE(pg_catalog.jsonb_agg(pg_catalog.jsonb_build_array(
            item_id,source_id,prepared_version_id,evidence_id,outcome,document_id,
            CASE WHEN outcome='extracted' THEN 'indexed' ELSE 'not_indexed' END
        ) ORDER BY item_id),'[]'::jsonb)
        INTO attempt_membership
        FROM public.brain_fileos_v2_document_attempt_items
        WHERE tenant_id=NEW.tenant_id AND attempt_id=attempt;
        SELECT COALESCE(pg_catalog.jsonb_agg(pg_catalog.jsonb_build_array(
            item_id,source_id,version_id,evidence_id,outcome,document_id,disposition
        ) ORDER BY item_id),'[]'::jsonb)
        INTO generation_membership
        FROM public.brain_index_generation_items
        WHERE tenant_id=NEW.tenant_id AND generation_id=NEW.generation_id;
        IF attempt_membership IS DISTINCT FROM generation_membership THEN
            RAISE EXCEPTION 'FileOS v2 index item membership is not exact';
        END IF;
        -- The OFFSET 0 LATERAL fence forces one primary-key probe per
        -- generation chunk. A wide anti-join or EXCEPT ALL can choose a
        -- population-sensitive plan under forced tenant RLS. The item ledger
        -- binds every base document to this generation, and the following
        -- count closes the reverse direction.
        SELECT count(*)::integer INTO unmatched_chunks
        FROM public.brain_index_generation_chunks g
        LEFT JOIN LATERAL (
            SELECT id,document_id,ordinal,start_offset,end_offset,text,sha256
            FROM public.brain_chunks c
            WHERE c.tenant_id=g.tenant_id AND c.id=g.id
            OFFSET 0
        ) c ON c.document_id=g.document_id AND c.ordinal=g.ordinal
           AND c.start_offset=g.start_offset AND c.end_offset=g.end_offset
           AND c.text=g.text AND c.sha256=g.sha256
        WHERE g.tenant_id=NEW.tenant_id AND g.generation_id=NEW.generation_id
          AND c.id IS NULL;
        SELECT COALESCE(sum(base.n),0)::integer INTO base_chunks
        FROM public.brain_index_generation_items i
        CROSS JOIN LATERAL (
            SELECT count(*)::integer AS n
            FROM public.brain_chunks c
            WHERE c.tenant_id=i.tenant_id AND c.document_id=i.document_id
        ) base
        WHERE i.tenant_id=NEW.tenant_id AND i.generation_id=NEW.generation_id;
        IF unmatched_chunks<>0 OR base_chunks<>actual_chunks THEN
            RAISE EXCEPTION 'FileOS v2 index chunks are not exact';
        END IF;
    END IF;
    RETURN NEW;
END
$function$;

COMMIT;
