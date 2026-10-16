BEGIN;

-- Extend the same DataCore index substrate, never the active read pointer.
ALTER TABLE public.brain_fileos_v2_later_run_completions
    ADD CONSTRAINT brain_fileos_v2_later_run_index_identity UNIQUE (
        tenant_id,id,attempt_id,source_id,run_sha256
    );
ALTER TABLE public.brain_index_generations
    ADD COLUMN v2_later_run_id uuid,
    ADD COLUMN v2_later_attempt_id uuid,
    ADD COLUMN v2_later_run_sha256 text CHECK (
        v2_later_run_sha256 IS NULL OR v2_later_run_sha256 ~ '^[a-f0-9]{64}$'
    ),
    ADD COLUMN v2_later_attempt_sha256 text CHECK (
        v2_later_attempt_sha256 IS NULL OR v2_later_attempt_sha256 ~ '^[a-f0-9]{64}$'
    ),
    ADD COLUMN v2_later_observation_counts jsonb;
ALTER TABLE public.brain_index_generations
    DROP CONSTRAINT brain_index_generations_basis_kind_check,
    ADD CONSTRAINT brain_index_generations_basis_kind_check
        CHECK (basis_kind IN ('v1','v2','v2_later')),
    DROP CONSTRAINT brain_index_generations_item_count_check,
    ADD CONSTRAINT brain_index_generations_item_count_check CHECK (
        (basis_kind='v1' AND item_count BETWEEN 0 AND 10000)
        OR (basis_kind IN ('v2','v2_later') AND item_count BETWEEN 0 AND 20000)
    ),
    DROP CONSTRAINT brain_index_generations_exact_basis,
    ADD CONSTRAINT brain_index_generations_exact_basis CHECK (
        (basis_kind='v1' AND run_actor_id IS NOT NULL AND run_id IS NOT NULL
         AND v2_stage_id IS NULL AND v2_completion_id IS NULL
         AND v2_attempt_id IS NULL AND v2_completion_sha256 IS NULL
         AND v2_attempt_sha256 IS NULL AND v2_policy_sha256 IS NULL
         AND v2_stage_counts IS NULL AND v2_later_run_id IS NULL
         AND v2_later_attempt_id IS NULL AND v2_later_run_sha256 IS NULL
         AND v2_later_attempt_sha256 IS NULL AND v2_later_observation_counts IS NULL)
        OR
        (basis_kind='v2' AND run_actor_id IS NULL AND run_id IS NULL
         AND v2_stage_id IS NOT NULL AND v2_completion_id IS NOT NULL
         AND v2_attempt_id IS NOT NULL AND v2_completion_sha256 IS NOT NULL
         AND v2_attempt_sha256 IS NOT NULL AND v2_policy_sha256 IS NOT NULL
         AND jsonb_typeof(v2_stage_counts)='object'
         AND v2_later_run_id IS NULL AND v2_later_attempt_id IS NULL
         AND v2_later_run_sha256 IS NULL AND v2_later_attempt_sha256 IS NULL
         AND v2_later_observation_counts IS NULL)
        OR
        (basis_kind='v2_later' AND run_actor_id IS NULL AND run_id IS NULL
         AND v2_stage_id IS NULL AND v2_completion_id IS NULL
         AND v2_attempt_id IS NULL AND v2_completion_sha256 IS NULL
         AND v2_attempt_sha256 IS NULL AND v2_policy_sha256 IS NULL
         AND v2_stage_counts IS NULL AND v2_later_run_id IS NOT NULL
         AND v2_later_attempt_id IS NOT NULL AND v2_later_run_sha256 IS NOT NULL
         AND v2_later_attempt_sha256 IS NOT NULL
         AND jsonb_typeof(v2_later_observation_counts)='object')
    ),
    ADD CONSTRAINT brain_index_generation_v2_later_run_basis FOREIGN KEY (
        tenant_id,v2_later_run_id,v2_later_attempt_id,source_id,v2_later_run_sha256
    ) REFERENCES public.brain_fileos_v2_later_run_completions (
        tenant_id,id,attempt_id,source_id,run_sha256
    );
CREATE UNIQUE INDEX brain_index_generation_v2_later_plan_unique
    ON public.brain_index_generations(
        tenant_id,source_id,v2_later_run_id,v2_later_attempt_id,plan_sha256
    ) WHERE basis_kind='v2_later';

CREATE FUNCTION public.guard_fileos_v2_later_index_generation() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
DECLARE run_row record;
DECLARE preparation_row record;
DECLARE prior_actor uuid;
DECLARE prior_run uuid;
DECLARE prior_observed timestamptz;
DECLARE latest_actor uuid;
DECLARE latest_run uuid;
DECLARE latest_observed timestamptz;
DECLARE latest_root text;
DECLARE source_root text;
BEGIN
    IF NEW.basis_kind <> 'v2_later' THEN RETURN NEW; END IF;
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
        NEW.tenant_id::text || ':fileos-source:' || NEW.source_id,0));
    SELECT r.attempt_id,r.attempt_sha256,r.observed_at,r.run_sha256,
           r.processed_counts,r.packet_id,r.preparation_id,r.baseline_completion_id,
           r.root_binding_sha256,a.ready
      INTO run_row
    FROM public.brain_fileos_v2_later_run_completions r
    JOIN public.brain_fileos_v2_later_document_attempts a
      ON a.tenant_id=r.tenant_id AND a.id=r.attempt_id
    WHERE r.tenant_id=NEW.tenant_id AND r.id=NEW.v2_later_run_id
      AND r.attempt_id=NEW.v2_later_attempt_id
      AND r.source_id=NEW.source_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'invalid FileOS v2 later index basis';
    END IF;
    SELECT hashed_count,packet_id,source_id,root_binding_sha256
      INTO preparation_row
    FROM public.brain_fileos_v2_later_evidence_preparations
    WHERE tenant_id=NEW.tenant_id AND id=run_row.preparation_id;
    IF run_row.run_sha256 IS NULL OR run_row.ready IS DISTINCT FROM true
       OR run_row.attempt_sha256 IS DISTINCT FROM NEW.v2_later_attempt_sha256
       OR run_row.run_sha256 IS DISTINCT FROM NEW.v2_later_run_sha256
       OR run_row.observed_at IS DISTINCT FROM NEW.observed_at
       OR run_row.processed_counts IS NULL
       OR preparation_row.hashed_count IS DISTINCT FROM NEW.item_count
       OR preparation_row.packet_id IS DISTINCT FROM run_row.packet_id
       OR preparation_row.source_id IS DISTINCT FROM NEW.source_id
       OR preparation_row.root_binding_sha256
          IS DISTINCT FROM run_row.root_binding_sha256 THEN
        RAISE EXCEPTION 'invalid FileOS v2 later index basis';
    END IF;
    IF NEW.v2_later_observation_counts IS DISTINCT FROM (
        SELECT p.packet->'candidate'->'counts'
        FROM public.brain_fileos_v2_later_observation_packets p
        WHERE p.tenant_id=NEW.tenant_id AND p.id=run_row.packet_id
    ) THEN
        RAISE EXCEPTION 'invalid FileOS v2 later index counts';
    END IF;
    SELECT c.prior_run_id,s.prior_actor_id,s.prior_observed_at
      INTO prior_run,prior_actor,prior_observed
    FROM public.brain_fileos_v2_baseline_completions c
    JOIN public.brain_fileos_v2_staged_inventories s
      ON s.tenant_id=c.tenant_id AND s.id=c.stage_id
    WHERE c.tenant_id=NEW.tenant_id AND c.id=run_row.baseline_completion_id;
    SELECT actor_id,run_id,observed_at,root_binding_sha256
      INTO latest_actor,latest_run,latest_observed,latest_root
    FROM public.brain_fileos_run_receipts
    WHERE tenant_id=NEW.tenant_id AND source_id=NEW.source_id
    ORDER BY observed_at DESC,completed_at DESC,run_id DESC LIMIT 1;
    SELECT root_binding_sha256 INTO source_root FROM public.brain_sources
    WHERE tenant_id=NEW.tenant_id AND id=NEW.source_id AND kind='fileos';
    IF prior_run IS NULL OR latest_actor IS DISTINCT FROM prior_actor
       OR latest_run IS DISTINCT FROM prior_run
       OR latest_observed IS DISTINCT FROM prior_observed
       OR latest_root IS DISTINCT FROM run_row.root_binding_sha256
       OR source_root IS DISTINCT FROM run_row.root_binding_sha256 THEN
        RAISE EXCEPTION 'stale FileOS v2 later index basis';
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER fileos_v2_later_index_source_lock
    BEFORE INSERT ON public.brain_index_generations FOR EACH ROW
    EXECUTE FUNCTION public.guard_fileos_v2_later_index_generation();

-- The existing generic receipt check closes counts. This additional check
-- binds every hashed attempt row and every generated chunk to its DataCore
-- base; hashless/excluded rows remain in the run ledger, not fake index items.
CREATE FUNCTION public.enforce_fileos_v2_later_index_ready() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
DECLARE later_attempt uuid;
DECLARE expected_membership jsonb;
DECLARE generation_membership jsonb;
DECLARE unmatched_chunks integer;
DECLARE base_chunks integer;
DECLARE actual_chunks integer;
BEGIN
    SELECT v2_later_attempt_id INTO later_attempt
    FROM public.brain_index_generations
    WHERE tenant_id=NEW.tenant_id AND id=NEW.generation_id
      AND source_id=NEW.source_id AND basis_kind='v2_later';
    IF later_attempt IS NULL THEN RETURN NEW; END IF;
    SELECT COALESCE(pg_catalog.jsonb_agg(pg_catalog.jsonb_build_array(
        item_id,source_id,prepared_version_id,evidence_id,outcome,document_id,
        CASE WHEN outcome='extracted' THEN 'indexed' ELSE 'not_indexed' END
    ) ORDER BY item_id),'[]'::jsonb) INTO expected_membership
    FROM public.brain_fileos_v2_later_document_attempt_items
    WHERE tenant_id=NEW.tenant_id AND attempt_id=later_attempt AND kind='hashed';
    SELECT COALESCE(pg_catalog.jsonb_agg(pg_catalog.jsonb_build_array(
        item_id,source_id,version_id,evidence_id,outcome,document_id,disposition
    ) ORDER BY item_id),'[]'::jsonb) INTO generation_membership
    FROM public.brain_index_generation_items
    WHERE tenant_id=NEW.tenant_id AND generation_id=NEW.generation_id;
    IF expected_membership IS DISTINCT FROM generation_membership THEN
        RAISE EXCEPTION 'FileOS v2 later index item membership is not exact';
    END IF;
    SELECT count(*)::integer INTO unmatched_chunks
    FROM public.brain_index_generation_chunks g
    LEFT JOIN LATERAL (
        SELECT id,document_id,ordinal,start_offset,end_offset,text,sha256
        FROM public.brain_chunks c
        WHERE c.tenant_id=g.tenant_id AND c.id=g.id OFFSET 0
    ) c ON c.document_id=g.document_id AND c.ordinal=g.ordinal
       AND c.start_offset=g.start_offset AND c.end_offset=g.end_offset
       AND c.text=g.text AND c.sha256=g.sha256
    WHERE g.tenant_id=NEW.tenant_id AND g.generation_id=NEW.generation_id
      AND c.id IS NULL;
    SELECT COALESCE(sum(base.n),0)::integer INTO base_chunks
    FROM public.brain_index_generation_items i
    CROSS JOIN LATERAL (
        SELECT count(*)::integer AS n FROM public.brain_chunks c
        WHERE c.tenant_id=i.tenant_id AND c.document_id=i.document_id
    ) base
    WHERE i.tenant_id=NEW.tenant_id AND i.generation_id=NEW.generation_id;
    SELECT count(*)::integer INTO actual_chunks
    FROM public.brain_index_generation_chunks
    WHERE tenant_id=NEW.tenant_id AND generation_id=NEW.generation_id;
    IF unmatched_chunks<>0 OR base_chunks<>actual_chunks THEN
        RAISE EXCEPTION 'FileOS v2 later index chunks are not exact';
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER fileos_v2_later_index_ready_exact
    BEFORE INSERT ON public.brain_index_generation_receipts FOR EACH ROW
    EXECUTE FUNCTION public.enforce_fileos_v2_later_index_ready();

-- ADR-131's indexed v2 count path is necessary for later generations too.
-- Preserve the v1 and baseline-v2 rules; the separate trigger above supplies
-- later exact membership and chunk closure.
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
    IF basis IN ('v2','v2_later') THEN
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
        SELECT count(*)::integer INTO unmatched_chunks
        FROM public.brain_index_generation_chunks g
        LEFT JOIN LATERAL (
            SELECT id,document_id,ordinal,start_offset,end_offset,text,sha256
            FROM public.brain_chunks c
            WHERE c.tenant_id=g.tenant_id AND c.id=g.id OFFSET 0
        ) c ON c.document_id=g.document_id AND c.ordinal=g.ordinal
           AND c.start_offset=g.start_offset AND c.end_offset=g.end_offset
           AND c.text=g.text AND c.sha256=g.sha256
        WHERE g.tenant_id=NEW.tenant_id AND g.generation_id=NEW.generation_id
          AND c.id IS NULL;
        SELECT COALESCE(sum(base.n),0)::integer INTO base_chunks
        FROM public.brain_index_generation_items i
        CROSS JOIN LATERAL (
            SELECT count(*)::integer AS n FROM public.brain_chunks c
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

CREATE FUNCTION public.refuse_fileos_v2_later_index_activation() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
BEGIN
    IF EXISTS (
        SELECT 1 FROM public.brain_index_generations
        WHERE tenant_id=NEW.tenant_id AND id=NEW.generation_id
          AND source_id=NEW.source_id AND basis_kind='v2_later'
    ) THEN
        RAISE EXCEPTION 'FileOS v2 later index activation is not authorized';
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER fileos_v2_later_index_activation_refused
    BEFORE INSERT ON public.brain_index_activations FOR EACH ROW
    EXECUTE FUNCTION public.refuse_fileos_v2_later_index_activation();

COMMIT;
