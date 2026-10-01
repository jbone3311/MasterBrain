BEGIN;

-- Keep one DataCore generation/chunk/activation substrate. Old rows remain v1.
ALTER TABLE public.brain_index_generations
    ADD COLUMN basis_kind text NOT NULL DEFAULT 'v1'
        CHECK (basis_kind IN ('v1','v2')),
    ADD COLUMN v2_stage_id uuid,
    ADD COLUMN v2_completion_id uuid,
    ADD COLUMN v2_attempt_id uuid,
    ADD COLUMN v2_completion_sha256 text
        CHECK (v2_completion_sha256 IS NULL OR v2_completion_sha256 ~ '^[a-f0-9]{64}$'),
    ADD COLUMN v2_attempt_sha256 text
        CHECK (v2_attempt_sha256 IS NULL OR v2_attempt_sha256 ~ '^[a-f0-9]{64}$'),
    ADD COLUMN v2_policy_sha256 text
        CHECK (v2_policy_sha256 IS NULL OR v2_policy_sha256 ~ '^[a-f0-9]{64}$'),
    ADD COLUMN v2_stage_counts jsonb;
ALTER TABLE public.brain_index_generations
    ALTER COLUMN run_actor_id DROP NOT NULL,
    ALTER COLUMN run_id DROP NOT NULL,
    DROP CONSTRAINT brain_index_generations_item_count_check,
    ADD CONSTRAINT brain_index_generations_item_count_check
        CHECK (item_count BETWEEN 0 AND 20000),
    ADD CONSTRAINT brain_index_generations_exact_basis CHECK (
        (basis_kind='v1' AND run_actor_id IS NOT NULL AND run_id IS NOT NULL
         AND v2_stage_id IS NULL AND v2_completion_id IS NULL
         AND v2_attempt_id IS NULL AND v2_completion_sha256 IS NULL
         AND v2_attempt_sha256 IS NULL AND v2_policy_sha256 IS NULL
         AND v2_stage_counts IS NULL)
        OR
        (basis_kind='v2' AND run_actor_id IS NULL AND run_id IS NULL
         AND v2_stage_id IS NOT NULL AND v2_completion_id IS NOT NULL
         AND v2_attempt_id IS NOT NULL AND v2_completion_sha256 IS NOT NULL
         AND v2_attempt_sha256 IS NOT NULL AND v2_policy_sha256 IS NOT NULL
         AND jsonb_typeof(v2_stage_counts)='object')
    ),
    ADD CONSTRAINT brain_index_generation_v2_attempt_basis FOREIGN KEY (
        tenant_id,v2_attempt_id,v2_completion_id,v2_stage_id,source_id
    ) REFERENCES public.brain_fileos_v2_document_attempts (
        tenant_id,id,completion_id,stage_id,source_id
    );
CREATE UNIQUE INDEX brain_index_generation_v2_plan_unique
    ON public.brain_index_generations(
        tenant_id,source_id,v2_completion_id,v2_attempt_id,plan_sha256
    ) WHERE basis_kind='v2';

-- A direct SQL writer cannot label a stale/unready v2 basis as a generation.
CREATE FUNCTION public.guard_fileos_v2_index_generation() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
DECLARE attempt_ready boolean;
DECLARE attempt_sha text;
DECLARE completion_sha text;
DECLARE policy_sha text;
DECLARE completed_counts jsonb;
DECLARE completed_observed timestamptz;
DECLARE prior_actor uuid;
DECLARE prior_run uuid;
DECLARE prior_observed timestamptz;
DECLARE root_binding text;
DECLARE hashed_count integer;
DECLARE latest_actor uuid;
DECLARE latest_run uuid;
DECLARE latest_observed timestamptz;
DECLARE latest_root text;
DECLARE source_root text;
BEGIN
    IF NEW.basis_kind <> 'v2' THEN RETURN NEW; END IF;
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
        NEW.tenant_id::text || ':fileos-source:' || NEW.source_id,0));
    SELECT a.ready,a.attempt_sha256,c.completion_sha256,c.policy_sha256,
           c.counts,c.fresh_observed_at,s.prior_actor_id,c.prior_run_id,
           s.prior_observed_at,c.root_binding_sha256,c.hashed_count
      INTO attempt_ready,attempt_sha,completion_sha,policy_sha,
           completed_counts,completed_observed,prior_actor,prior_run,
           prior_observed,root_binding,hashed_count
    FROM public.brain_fileos_v2_document_attempts a
    JOIN public.brain_fileos_v2_baseline_completions c
      ON c.tenant_id=a.tenant_id AND c.id=a.completion_id
    JOIN public.brain_fileos_v2_staged_inventories s
      ON s.tenant_id=c.tenant_id AND s.id=c.stage_id
    WHERE a.tenant_id=NEW.tenant_id AND a.id=NEW.v2_attempt_id
      AND a.completion_id=NEW.v2_completion_id
      AND a.stage_id=NEW.v2_stage_id AND a.source_id=NEW.source_id;
    IF NOT FOUND OR attempt_ready IS DISTINCT FROM true
       OR attempt_sha IS DISTINCT FROM NEW.v2_attempt_sha256
       OR completion_sha IS DISTINCT FROM NEW.v2_completion_sha256
       OR policy_sha IS DISTINCT FROM NEW.v2_policy_sha256
       OR completed_counts IS DISTINCT FROM NEW.v2_stage_counts
       OR completed_observed IS DISTINCT FROM NEW.observed_at
       OR hashed_count IS DISTINCT FROM NEW.item_count THEN
        RAISE EXCEPTION 'invalid FileOS v2 index basis';
    END IF;
    SELECT actor_id,run_id,observed_at,root_binding_sha256
      INTO latest_actor,latest_run,latest_observed,latest_root
    FROM public.brain_fileos_run_receipts
    WHERE tenant_id=NEW.tenant_id AND source_id=NEW.source_id
    ORDER BY observed_at DESC,completed_at DESC,run_id DESC LIMIT 1;
    SELECT root_binding_sha256 INTO source_root FROM public.brain_sources
    WHERE tenant_id=NEW.tenant_id AND id=NEW.source_id AND kind='fileos';
    IF latest_actor IS DISTINCT FROM prior_actor
       OR latest_run IS DISTINCT FROM prior_run
       OR latest_observed IS DISTINCT FROM prior_observed
       OR latest_root IS DISTINCT FROM root_binding
       OR source_root IS DISTINCT FROM root_binding THEN
        RAISE EXCEPTION 'stale FileOS v2 index basis';
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER fileos_v2_index_generation_source_lock
    BEFORE INSERT ON public.brain_index_generations FOR EACH ROW
    EXECUTE FUNCTION public.guard_fileos_v2_index_generation();

-- Use the child row's source identity, even when its generation parent is an
-- uncommitted concurrent insert. Otherwise a child could pass a pre-lock
-- readiness check, wait for that parent FK, then append after its receipt.
CREATE FUNCTION public.lock_fileos_v2_index_child() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
BEGIN
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
        NEW.tenant_id::text || ':fileos-source:' || NEW.source_id,0));
    RETURN NEW;
END
$function$;
CREATE TRIGGER a_fileos_v2_index_item_lock
    BEFORE INSERT ON public.brain_index_generation_items FOR EACH ROW
    EXECUTE FUNCTION public.lock_fileos_v2_index_child();
CREATE TRIGGER a_fileos_v2_index_chunk_lock
    BEFORE INSERT ON public.brain_index_generation_chunks FOR EACH ROW
    EXECUTE FUNCTION public.lock_fileos_v2_index_child();
CREATE TRIGGER a_fileos_v2_index_ready_lock
    BEFORE INSERT ON public.brain_index_generation_receipts FOR EACH ROW
    EXECUTE FUNCTION public.lock_fileos_v2_index_child();

-- Preserve ADR-058 v1 validation; add exact v2 attempt and base-chunk closure.
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
        SELECT count(*)::integer INTO unmatched_chunks
        FROM public.brain_index_generation_chunks g
        LEFT JOIN public.brain_chunks c
          ON c.tenant_id=g.tenant_id AND c.id=g.id AND c.document_id=g.document_id
         AND c.ordinal=g.ordinal AND c.start_offset=g.start_offset
         AND c.end_offset=g.end_offset AND c.text=g.text AND c.sha256=g.sha256
        WHERE g.tenant_id=NEW.tenant_id AND g.generation_id=NEW.generation_id
          AND c.id IS NULL;
        SELECT count(*)::integer INTO base_chunks
        FROM public.brain_index_generation_items i
        JOIN public.brain_chunks c
          ON c.tenant_id=i.tenant_id AND c.document_id=i.document_id
        WHERE i.tenant_id=NEW.tenant_id AND i.generation_id=NEW.generation_id;
        IF unmatched_chunks<>0 OR base_chunks<>actual_chunks THEN
            RAISE EXCEPTION 'FileOS v2 index chunks are not exact';
        END IF;
    END IF;
    RETURN NEW;
END
$function$;

CREATE FUNCTION public.refuse_fileos_v2_index_activation() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
BEGIN
    IF EXISTS (
        SELECT 1 FROM public.brain_index_generations
        WHERE tenant_id=NEW.tenant_id AND id=NEW.generation_id
          AND source_id=NEW.source_id AND basis_kind='v2'
    ) THEN
        RAISE EXCEPTION 'FileOS v2 index activation is not authorized';
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER fileos_v2_index_activation_refused
    BEFORE INSERT ON public.brain_index_activations FOR EACH ROW
    EXECUTE FUNCTION public.refuse_fileos_v2_index_activation();

COMMIT;
