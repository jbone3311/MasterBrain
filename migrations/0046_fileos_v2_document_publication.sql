BEGIN;

-- V2 document attempts are historical derivatives of a completed baseline.
-- No existing v1 current pointer, generation or activation references them.
ALTER TABLE public.brain_fileos_v2_baseline_completions
    ADD CONSTRAINT brain_fileos_v2_completion_document_identity UNIQUE (
        tenant_id,id,stage_id,source_id,prior_run_id,root_binding_sha256,
        completion_sha256,hashed_count
    );
ALTER TABLE public.brain_fileos_v2_prepared_rows
    ADD CONSTRAINT brain_fileos_v2_prepared_document_identity UNIQUE (
        tenant_id,stage_id,source_id,locator,item_id,candidate_version_id,
        prepared_version_id,evidence_id
    );

CREATE TABLE public.brain_fileos_v2_document_attempts (
    tenant_id uuid NOT NULL,
    id uuid NOT NULL,
    actor_id uuid NOT NULL,
    completion_id uuid NOT NULL,
    stage_id uuid NOT NULL,
    source_id text NOT NULL,
    prior_run_id uuid NOT NULL,
    root_binding_sha256 text NOT NULL CHECK (root_binding_sha256 ~ '^[a-f0-9]{64}$'),
    completion_sha256 text NOT NULL CHECK (completion_sha256 ~ '^[a-f0-9]{64}$'),
    hashed_count integer NOT NULL CHECK (hashed_count BETWEEN 0 AND 20000),
    code_revision text NOT NULL CHECK (length(code_revision) BETWEEN 1 AND 200),
    text_extractor_version text NOT NULL CHECK (length(text_extractor_version) BETWEEN 1 AND 200),
    document_processor_version text CHECK (
        document_processor_version IS NULL OR
        length(document_processor_version) BETWEEN 1 AND 200
    ),
    counts jsonb NOT NULL CHECK (
        jsonb_typeof(counts) = 'object'
        AND counts ?& ARRAY['extracted','empty','unsupported','deferred','changed','failed']
        AND counts = jsonb_build_object(
            'extracted',counts->'extracted','empty',counts->'empty',
            'unsupported',counts->'unsupported','deferred',counts->'deferred',
            'changed',counts->'changed','failed',counts->'failed')
        AND (counts->>'extracted') ~ '^(0|[1-9][0-9]*)$'
        AND (counts->>'empty') ~ '^(0|[1-9][0-9]*)$'
        AND (counts->>'unsupported') ~ '^(0|[1-9][0-9]*)$'
        AND (counts->>'deferred') ~ '^(0|[1-9][0-9]*)$'
        AND (counts->>'changed') ~ '^(0|[1-9][0-9]*)$'
        AND (counts->>'failed') ~ '^(0|[1-9][0-9]*)$'
        AND jsonb_typeof(counts->'extracted') = 'number'
        AND jsonb_typeof(counts->'empty') = 'number'
        AND jsonb_typeof(counts->'unsupported') = 'number'
        AND jsonb_typeof(counts->'deferred') = 'number'
        AND jsonb_typeof(counts->'changed') = 'number'
        AND jsonb_typeof(counts->'failed') = 'number'
        AND (counts->>'extracted')::integer <= 20000
        AND (counts->>'empty')::integer <= 20000
        AND (counts->>'unsupported')::integer <= 20000
        AND (counts->>'deferred')::integer <= 20000
        AND (counts->>'changed')::integer <= 20000
        AND (counts->>'failed')::integer <= 20000
        AND (counts->>'extracted')::integer + (counts->>'empty')::integer
          + (counts->>'unsupported')::integer + (counts->>'deferred')::integer
          + (counts->>'changed')::integer + (counts->>'failed')::integer = hashed_count
    ),
    ready boolean NOT NULL CHECK (
        ready = ((counts->>'changed')::integer = 0 AND (counts->>'failed')::integer = 0)
    ),
    observed_at timestamptz NOT NULL,
    attempt_sha256 text NOT NULL CHECK (attempt_sha256 ~ '^[a-f0-9]{64}$'),
    completed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    UNIQUE (tenant_id,id,completion_id,stage_id,source_id),
    CHECK (observed_at > '-infinity'::timestamptz),
    FOREIGN KEY (
        tenant_id,completion_id,stage_id,source_id,prior_run_id,
        root_binding_sha256,completion_sha256,hashed_count
    ) REFERENCES public.brain_fileos_v2_baseline_completions (
        tenant_id,id,stage_id,source_id,prior_run_id,
        root_binding_sha256,completion_sha256,hashed_count
    )
);
CREATE UNIQUE INDEX brain_fileos_v2_one_ready_document_attempt
    ON public.brain_fileos_v2_document_attempts(tenant_id,completion_id)
    WHERE ready;

CREATE TABLE public.brain_fileos_v2_document_attempt_items (
    tenant_id uuid NOT NULL,
    attempt_id uuid NOT NULL,
    completion_id uuid NOT NULL,
    stage_id uuid NOT NULL,
    source_id text NOT NULL,
    locator text NOT NULL,
    item_id text NOT NULL,
    candidate_version_id text NOT NULL,
    prepared_version_id text NOT NULL,
    evidence_id text NOT NULL,
    outcome text NOT NULL CHECK (
        outcome IN ('extracted','empty','unsupported','deferred','changed','failed')
    ),
    document_id text,
    PRIMARY KEY (tenant_id,attempt_id,locator),
    CHECK ((outcome='extracted')=(document_id IS NOT NULL)),
    FOREIGN KEY (tenant_id,attempt_id,completion_id,stage_id,source_id)
        REFERENCES public.brain_fileos_v2_document_attempts(
            tenant_id,id,completion_id,stage_id,source_id
        ) DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY (
        tenant_id,stage_id,source_id,locator,item_id,candidate_version_id,
        prepared_version_id,evidence_id
    ) REFERENCES public.brain_fileos_v2_prepared_rows (
        tenant_id,stage_id,source_id,locator,item_id,candidate_version_id,
        prepared_version_id,evidence_id
    ),
    FOREIGN KEY (tenant_id,document_id,evidence_id)
        REFERENCES public.brain_normalized_documents(tenant_id,id,evidence_id)
);

CREATE FUNCTION public.guard_fileos_v2_document_attempt() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
DECLARE prior_actor uuid;
DECLARE prior_observed timestamptz;
DECLARE latest_actor uuid;
DECLARE latest_run uuid;
DECLARE latest_observed timestamptz;
DECLARE latest_root text;
DECLARE source_root text;
DECLARE completed_observed timestamptz;
BEGIN
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
        NEW.tenant_id::text || ':fileos-source:' || NEW.source_id,0));
    SELECT s.prior_actor_id,s.prior_observed_at,c.fresh_observed_at
      INTO prior_actor,prior_observed,completed_observed
    FROM public.brain_fileos_v2_baseline_completions c
    JOIN public.brain_fileos_v2_staged_inventories s
      ON s.tenant_id=c.tenant_id AND s.id=c.stage_id
    WHERE c.tenant_id=NEW.tenant_id AND c.id=NEW.completion_id
      AND c.stage_id=NEW.stage_id AND c.source_id=NEW.source_id;
    SELECT actor_id,run_id,observed_at,root_binding_sha256
      INTO latest_actor,latest_run,latest_observed,latest_root
    FROM public.brain_fileos_run_receipts
    WHERE tenant_id=NEW.tenant_id AND source_id=NEW.source_id
    ORDER BY observed_at DESC,completed_at DESC,run_id DESC LIMIT 1;
    SELECT root_binding_sha256 INTO source_root
    FROM public.brain_sources
    WHERE tenant_id=NEW.tenant_id AND id=NEW.source_id AND kind='fileos';
    IF prior_actor IS NULL OR latest_actor IS DISTINCT FROM prior_actor
       OR latest_run IS DISTINCT FROM NEW.prior_run_id
       OR latest_observed IS DISTINCT FROM prior_observed
       OR latest_root IS DISTINCT FROM NEW.root_binding_sha256
       OR source_root IS DISTINCT FROM NEW.root_binding_sha256
       OR NEW.observed_at <= completed_observed THEN
        RAISE EXCEPTION 'stale FileOS v2 document attempt';
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER fileos_v2_document_attempt_source_lock
    BEFORE INSERT ON public.brain_fileos_v2_document_attempts FOR EACH ROW
    EXECUTE FUNCTION public.guard_fileos_v2_document_attempt();

CREATE FUNCTION public.enforce_fileos_v2_document_attempt_ledger() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
DECLARE actual_counts jsonb;
DECLARE missing_count integer;
DECLARE wrong_document_count integer;
BEGIN
    SELECT pg_catalog.jsonb_build_object(
        'extracted',count(*) FILTER (WHERE outcome='extracted'),
        'empty',count(*) FILTER (WHERE outcome='empty'),
        'unsupported',count(*) FILTER (WHERE outcome='unsupported'),
        'deferred',count(*) FILTER (WHERE outcome='deferred'),
        'changed',count(*) FILTER (WHERE outcome='changed'),
        'failed',count(*) FILTER (WHERE outcome='failed'))
    INTO actual_counts FROM public.brain_fileos_v2_document_attempt_items
    WHERE tenant_id=NEW.tenant_id AND attempt_id=NEW.id;
    IF actual_counts IS DISTINCT FROM NEW.counts THEN
        RAISE EXCEPTION 'invalid FileOS v2 document attempt counts';
    END IF;
    SELECT count(*)::integer INTO missing_count
    FROM public.brain_fileos_v2_prepared_rows p
    LEFT JOIN public.brain_fileos_v2_document_attempt_items i
      ON i.tenant_id=p.tenant_id AND i.attempt_id=NEW.id
     AND i.stage_id=p.stage_id AND i.locator=p.locator
    WHERE p.tenant_id=NEW.tenant_id AND p.stage_id=NEW.stage_id
      AND i.locator IS NULL;
    IF missing_count <> 0 THEN
        RAISE EXCEPTION 'incomplete FileOS v2 document attempt';
    END IF;
    SELECT count(*)::integer INTO wrong_document_count
    FROM public.brain_fileos_v2_document_attempt_items i
    JOIN public.brain_normalized_documents d
      ON d.tenant_id=i.tenant_id AND d.id=i.document_id
    WHERE i.tenant_id=NEW.tenant_id AND i.attempt_id=NEW.id
      AND i.outcome='extracted'
      AND d.normalizer NOT IN (
          NEW.text_extractor_version,
          COALESCE(NEW.document_processor_version,NEW.text_extractor_version)
      );
    IF wrong_document_count <> 0 THEN
        RAISE EXCEPTION 'invalid FileOS v2 document provenance';
    END IF;
    RETURN NULL;
END
$function$;
CREATE CONSTRAINT TRIGGER fileos_v2_document_attempt_ledger
    AFTER INSERT ON public.brain_fileos_v2_document_attempts
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION public.enforce_fileos_v2_document_attempt_ledger();

CREATE FUNCTION public.refuse_late_fileos_v2_document_attempt_item() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
BEGIN
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
        NEW.tenant_id::text || ':fileos-source:' || NEW.source_id,0));
    IF EXISTS (SELECT 1 FROM public.brain_fileos_v2_document_attempts
               WHERE tenant_id=NEW.tenant_id AND id=NEW.attempt_id) THEN
        RAISE EXCEPTION 'sealed FileOS v2 document attempt';
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER fileos_v2_document_attempt_item_closed
    BEFORE INSERT ON public.brain_fileos_v2_document_attempt_items FOR EACH ROW
    EXECUTE FUNCTION public.refuse_late_fileos_v2_document_attempt_item();

DO $block$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'brain_fileos_v2_document_attempts',
        'brain_fileos_v2_document_attempt_items'
    ] LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',table_name);
        EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY',table_name);
        EXECUTE format('CREATE POLICY tenant_isolation ON public.%I USING
            (tenant_id=nullif(current_setting(''email_brain.tenant_id'',true),'''')::uuid)
            WITH CHECK (tenant_id=nullif(current_setting(''email_brain.tenant_id'',true),'''')::uuid)',
            table_name);
        EXECUTE format('CREATE POLICY tenant_login_fence ON public.%I AS RESTRICTIVE
            FOR ALL TO PUBLIC USING (public.masterbrain_tenant_login_allows(tenant_id))
            WITH CHECK (public.masterbrain_tenant_login_allows(tenant_id))',table_name);
        EXECUTE format('CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON public.%I
            FOR EACH ROW EXECUTE FUNCTION public.deny_evidence_mutation()',table_name);
        EXECUTE format('CREATE TRIGGER protected_no_truncate BEFORE TRUNCATE ON public.%I
            FOR EACH STATEMENT EXECUTE FUNCTION public.deny_protected_truncate()',table_name);
    END LOOP;
END $block$;

COMMIT;
