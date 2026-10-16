BEGIN;

-- A historical processing attempt over one exact later observation. It is
-- deliberately not a completed FileOS run, current index or absence source.
ALTER TABLE public.brain_fileos_v2_later_evidence_preparations
    ADD CONSTRAINT brain_fileos_v2_later_preparation_document_identity UNIQUE (
        tenant_id,id,closure_id,packet_id,completion_id,source_id,
        root_binding_sha256,preparation_sha256
    );
ALTER TABLE public.brain_fileos_v2_later_prepared_rows
    ADD CONSTRAINT brain_fileos_v2_later_prepared_document_identity UNIQUE (
        tenant_id,preparation_id,source_id,locator,item_id,
        candidate_version_id,prepared_version_id,evidence_id
    );

CREATE TABLE public.brain_fileos_v2_later_document_attempts (
    tenant_id uuid NOT NULL,
    id uuid NOT NULL,
    actor_id uuid NOT NULL,
    preparation_id uuid NOT NULL,
    closure_id uuid NOT NULL,
    packet_id uuid NOT NULL,
    completion_id uuid NOT NULL,
    source_id text NOT NULL,
    root_binding_sha256 text NOT NULL CHECK (root_binding_sha256 ~ '^[a-f0-9]{64}$'),
    preparation_sha256 text NOT NULL CHECK (preparation_sha256 ~ '^[a-f0-9]{64}$'),
    code_revision text NOT NULL CHECK (length(code_revision) BETWEEN 1 AND 200),
    text_extractor_version text NOT NULL CHECK (length(text_extractor_version) BETWEEN 1 AND 200),
    document_processor_version text CHECK (
        document_processor_version IS NULL OR
        length(document_processor_version) BETWEEN 1 AND 200
    ),
    counts jsonb NOT NULL CHECK (
        jsonb_typeof(counts)='object'
        AND counts = jsonb_build_object(
            'extracted',counts->'extracted','empty',counts->'empty',
            'unsupported',counts->'unsupported','deferred',counts->'deferred',
            'changed',counts->'changed','failed',counts->'failed',
            'deferred_source',counts->'deferred_source',
            'excluded_source',counts->'excluded_source',
            'scan_error',counts->'scan_error'
        )
        AND (counts->>'extracted') ~ '^(0|[1-9][0-9]*)$'
        AND (counts->>'empty') ~ '^(0|[1-9][0-9]*)$'
        AND (counts->>'unsupported') ~ '^(0|[1-9][0-9]*)$'
        AND (counts->>'deferred') ~ '^(0|[1-9][0-9]*)$'
        AND (counts->>'changed') ~ '^(0|[1-9][0-9]*)$'
        AND (counts->>'failed') ~ '^(0|[1-9][0-9]*)$'
        AND (counts->>'deferred_source') ~ '^(0|[1-9][0-9]*)$'
        AND (counts->>'excluded_source') ~ '^(0|[1-9][0-9]*)$'
        AND (counts->>'scan_error') ~ '^(0|[1-9][0-9]*)$'
        AND jsonb_typeof(counts->'extracted')='number'
        AND jsonb_typeof(counts->'empty')='number'
        AND jsonb_typeof(counts->'unsupported')='number'
        AND jsonb_typeof(counts->'deferred')='number'
        AND jsonb_typeof(counts->'changed')='number'
        AND jsonb_typeof(counts->'failed')='number'
        AND jsonb_typeof(counts->'deferred_source')='number'
        AND jsonb_typeof(counts->'excluded_source')='number'
        AND jsonb_typeof(counts->'scan_error')='number'
        AND (counts->>'extracted')::integer <= 20000
        AND (counts->>'empty')::integer <= 20000
        AND (counts->>'unsupported')::integer <= 20000
        AND (counts->>'deferred')::integer <= 20000
        AND (counts->>'changed')::integer <= 20000
        AND (counts->>'failed')::integer <= 20000
        AND (counts->>'deferred_source')::integer <= 20000
        AND (counts->>'excluded_source')::integer <= 20000
        AND (counts->>'scan_error')::integer <= 20000
    ),
    ready boolean NOT NULL CHECK (
        ready = ((counts->>'changed')::integer=0
                 AND (counts->>'failed')::integer=0
                 AND (counts->>'scan_error')::integer=0)
    ),
    publishable boolean NOT NULL DEFAULT false CHECK (publishable=false),
    absence_authorized boolean NOT NULL DEFAULT false CHECK (absence_authorized=false),
    requires_review boolean NOT NULL DEFAULT true CHECK (requires_review=true),
    observed_at timestamptz NOT NULL,
    attempt_sha256 text NOT NULL CHECK (attempt_sha256 ~ '^[a-f0-9]{64}$'),
    completed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    UNIQUE (tenant_id,id,preparation_id,source_id),
    CHECK (observed_at > '-infinity'::timestamptz),
    FOREIGN KEY (
        tenant_id,preparation_id,closure_id,packet_id,completion_id,
        source_id,root_binding_sha256,preparation_sha256
    ) REFERENCES public.brain_fileos_v2_later_evidence_preparations (
        tenant_id,id,closure_id,packet_id,completion_id,source_id,
        root_binding_sha256,preparation_sha256
    )
);
CREATE UNIQUE INDEX brain_fileos_v2_later_one_ready_document_attempt
    ON public.brain_fileos_v2_later_document_attempts(tenant_id,preparation_id)
    WHERE ready;

CREATE TABLE public.brain_fileos_v2_later_document_attempt_items (
    tenant_id uuid NOT NULL,
    attempt_id uuid NOT NULL,
    preparation_id uuid NOT NULL,
    source_id text NOT NULL,
    locator text NOT NULL CHECK (length(locator) BETWEEN 1 AND 4000),
    kind text NOT NULL CHECK (kind IN ('hashed','deferred','excluded','error')),
    item_id text,
    candidate_version_id text,
    prepared_version_id text,
    evidence_id text,
    outcome text NOT NULL CHECK (
        outcome IN ('extracted','empty','unsupported','deferred','changed','failed',
                    'deferred_source','excluded_source','scan_error')
    ),
    document_id text,
    PRIMARY KEY (tenant_id,attempt_id,locator),
    CHECK (
        (kind='hashed' AND item_id IS NOT NULL AND candidate_version_id IS NOT NULL
         AND prepared_version_id IS NOT NULL AND evidence_id IS NOT NULL
         AND outcome IN ('extracted','empty','unsupported','deferred','changed','failed'))
        OR
        (kind<>'hashed' AND item_id IS NULL AND candidate_version_id IS NULL
         AND prepared_version_id IS NULL AND evidence_id IS NULL
         AND outcome=CASE kind WHEN 'deferred' THEN 'deferred_source'
                               WHEN 'excluded' THEN 'excluded_source'
                               ELSE 'scan_error' END)
    ),
    CHECK ((outcome='extracted')=(document_id IS NOT NULL)),
    FOREIGN KEY (tenant_id,attempt_id,preparation_id,source_id)
        REFERENCES public.brain_fileos_v2_later_document_attempts(
            tenant_id,id,preparation_id,source_id
        )
        DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY (
        tenant_id,preparation_id,source_id,locator,item_id,
        candidate_version_id,prepared_version_id,evidence_id
    ) REFERENCES public.brain_fileos_v2_later_prepared_rows (
        tenant_id,preparation_id,source_id,locator,item_id,
        candidate_version_id,prepared_version_id,evidence_id
    ),
    FOREIGN KEY (tenant_id,document_id,evidence_id)
        REFERENCES public.brain_normalized_documents(tenant_id,id,evidence_id)
);

CREATE FUNCTION public.guard_fileos_v2_later_document_attempt() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
DECLARE prior_run uuid;
DECLARE latest_run uuid;
DECLARE latest_root text;
DECLARE source_root text;
DECLARE prepared_observed timestamptz;
BEGIN
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
        NEW.tenant_id::text || ':fileos-source:' || NEW.source_id,0));
    SELECT c.prior_run_id,p.prepared_observed_at
      INTO prior_run,prepared_observed
    FROM public.brain_fileos_v2_later_evidence_preparations p
    JOIN public.brain_fileos_v2_baseline_completions c
      ON c.tenant_id=p.tenant_id AND c.id=p.completion_id
    WHERE p.tenant_id=NEW.tenant_id AND p.id=NEW.preparation_id
      AND p.source_id=NEW.source_id;
    SELECT run_id,root_binding_sha256 INTO latest_run,latest_root
    FROM public.brain_fileos_run_receipts
    WHERE tenant_id=NEW.tenant_id AND source_id=NEW.source_id
    ORDER BY observed_at DESC,completed_at DESC,run_id DESC LIMIT 1;
    SELECT root_binding_sha256 INTO source_root FROM public.brain_sources
    WHERE tenant_id=NEW.tenant_id AND id=NEW.source_id AND kind='fileos';
    IF prior_run IS NULL OR latest_run IS DISTINCT FROM prior_run
       OR latest_root IS DISTINCT FROM NEW.root_binding_sha256
       OR source_root IS DISTINCT FROM NEW.root_binding_sha256
       OR NEW.observed_at <= prepared_observed THEN
        RAISE EXCEPTION 'stale FileOS v2 later document attempt';
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER fileos_v2_later_document_source_lock
    BEFORE INSERT ON public.brain_fileos_v2_later_document_attempts FOR EACH ROW
    EXECUTE FUNCTION public.guard_fileos_v2_later_document_attempt();

CREATE FUNCTION public.enforce_fileos_v2_later_document_attempt() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
DECLARE closure_rows jsonb;
DECLARE actual_counts jsonb;
DECLARE actual_total integer;
DECLARE missing_count integer;
DECLARE bad_document_count integer;
BEGIN
    SELECT c.closure->'current_rows' INTO closure_rows
    FROM public.brain_fileos_v2_later_evidence_preparations p
    JOIN public.brain_fileos_v2_later_coverage_closures c
      ON c.tenant_id=p.tenant_id AND c.id=p.closure_id
    WHERE p.tenant_id=NEW.tenant_id AND p.id=NEW.preparation_id;
    SELECT pg_catalog.jsonb_build_object(
        'extracted',count(*) FILTER (WHERE outcome='extracted'),
        'empty',count(*) FILTER (WHERE outcome='empty'),
        'unsupported',count(*) FILTER (WHERE outcome='unsupported'),
        'deferred',count(*) FILTER (WHERE outcome='deferred'),
        'changed',count(*) FILTER (WHERE outcome='changed'),
        'failed',count(*) FILTER (WHERE outcome='failed'),
        'deferred_source',count(*) FILTER (WHERE outcome='deferred_source'),
        'excluded_source',count(*) FILTER (WHERE outcome='excluded_source'),
        'scan_error',count(*) FILTER (WHERE outcome='scan_error')),
        count(*)::integer
      INTO actual_counts,actual_total
    FROM public.brain_fileos_v2_later_document_attempt_items
    WHERE tenant_id=NEW.tenant_id AND attempt_id=NEW.id;
    IF closure_rows IS NULL OR actual_counts IS DISTINCT FROM NEW.counts
       OR actual_total <> pg_catalog.jsonb_array_length(closure_rows) THEN
        RAISE EXCEPTION 'invalid FileOS v2 later document attempt counts';
    END IF;
    SELECT count(*)::integer INTO missing_count
    FROM pg_catalog.jsonb_to_recordset(closure_rows) AS c(
        kind text, locator text, item_id text, candidate_version_id text
    )
    LEFT JOIN public.brain_fileos_v2_later_document_attempt_items i
      ON i.tenant_id=NEW.tenant_id AND i.attempt_id=NEW.id
     AND i.locator=c.locator AND i.kind=c.kind
     AND (c.kind<>'hashed' OR
          (i.item_id=c.item_id AND i.candidate_version_id=c.candidate_version_id))
    WHERE i.locator IS NULL;
    IF missing_count <> 0 THEN
        RAISE EXCEPTION 'incomplete FileOS v2 later document attempt';
    END IF;
    SELECT count(*)::integer INTO bad_document_count
    FROM public.brain_fileos_v2_later_document_attempt_items i
    JOIN public.brain_normalized_documents d
      ON d.tenant_id=i.tenant_id AND d.id=i.document_id
    WHERE i.tenant_id=NEW.tenant_id AND i.attempt_id=NEW.id
      AND i.outcome='extracted'
      AND d.normalizer NOT IN (
          NEW.text_extractor_version,
          COALESCE(NEW.document_processor_version,NEW.text_extractor_version)
      );
    IF bad_document_count <> 0 THEN
        RAISE EXCEPTION 'invalid FileOS v2 later document provenance';
    END IF;
    RETURN NULL;
END
$function$;
CREATE CONSTRAINT TRIGGER fileos_v2_later_document_attempt_complete
    AFTER INSERT ON public.brain_fileos_v2_later_document_attempts
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION public.enforce_fileos_v2_later_document_attempt();

CREATE FUNCTION public.refuse_late_fileos_v2_later_document_item() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
BEGIN
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
        NEW.tenant_id::text || ':fileos-source:' || NEW.source_id,0));
    IF EXISTS (SELECT 1 FROM public.brain_fileos_v2_later_document_attempts
               WHERE tenant_id=NEW.tenant_id AND id=NEW.attempt_id) THEN
        RAISE EXCEPTION 'sealed FileOS v2 later document attempt';
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER fileos_v2_later_document_item_closed
    BEFORE INSERT ON public.brain_fileos_v2_later_document_attempt_items FOR EACH ROW
    EXECUTE FUNCTION public.refuse_late_fileos_v2_later_document_item();

DO $block$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'brain_fileos_v2_later_document_attempts',
        'brain_fileos_v2_later_document_attempt_items'
    ] LOOP
        EXECUTE pg_catalog.format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',table_name);
        EXECUTE pg_catalog.format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY',table_name);
        EXECUTE pg_catalog.format(
            'CREATE POLICY tenant_isolation ON public.%I USING '
            || '(tenant_id=nullif(current_setting(''email_brain.tenant_id'',true),'''')::uuid) '
            || 'WITH CHECK (tenant_id=nullif(current_setting(''email_brain.tenant_id'',true),'''')::uuid)',
            table_name
        );
        EXECUTE pg_catalog.format(
            'CREATE POLICY tenant_login_fence ON public.%I AS RESTRICTIVE FOR ALL TO PUBLIC '
            || 'USING (public.masterbrain_tenant_login_allows(tenant_id)) '
            || 'WITH CHECK (public.masterbrain_tenant_login_allows(tenant_id))',table_name
        );
        EXECUTE pg_catalog.format(
            'CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON public.%I FOR EACH ROW '
            || 'EXECUTE FUNCTION public.deny_evidence_mutation()',table_name
        );
        EXECUTE pg_catalog.format(
            'CREATE TRIGGER protected_no_truncate BEFORE TRUNCATE ON public.%I FOR EACH STATEMENT '
            || 'EXECUTE FUNCTION public.deny_protected_truncate()',table_name
        );
    END LOOP;
END
$block$;

COMMIT;
