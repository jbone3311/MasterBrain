BEGIN;

-- A completed *historical* processing run. Neither current FileOS reads nor
-- absence/event writers consume this table. The ready document attempt is
-- necessary but not sufficient for a later activation decision.
ALTER TABLE public.brain_fileos_v2_later_document_attempts
    ADD CONSTRAINT brain_fileos_v2_later_attempt_run_identity UNIQUE (
        tenant_id,id,preparation_id,source_id,attempt_sha256,ready
    );
ALTER TABLE public.brain_fileos_v2_later_coverage_closures
    ADD CONSTRAINT brain_fileos_v2_later_coverage_run_identity UNIQUE (
        tenant_id,id,packet_id,source_id,closure_sha256
    );
ALTER TABLE public.brain_fileos_v2_later_observation_packets
    ADD CONSTRAINT brain_fileos_v2_later_packet_run_identity UNIQUE (
        tenant_id,id,completion_id,source_id,packet_sha256
    );

CREATE TABLE public.brain_fileos_v2_later_run_completions (
    tenant_id uuid NOT NULL,
    id uuid NOT NULL,
    actor_id uuid NOT NULL,
    attempt_id uuid NOT NULL,
    preparation_id uuid NOT NULL,
    closure_id uuid NOT NULL,
    packet_id uuid NOT NULL,
    baseline_completion_id uuid NOT NULL,
    source_id text NOT NULL,
    root_binding_sha256 text NOT NULL CHECK (root_binding_sha256 ~ '^[a-f0-9]{64}$'),
    attempt_sha256 text NOT NULL CHECK (attempt_sha256 ~ '^[a-f0-9]{64}$'),
    preparation_sha256 text NOT NULL CHECK (preparation_sha256 ~ '^[a-f0-9]{64}$'),
    closure_sha256 text NOT NULL CHECK (closure_sha256 ~ '^[a-f0-9]{64}$'),
    packet_sha256 text NOT NULL CHECK (packet_sha256 ~ '^[a-f0-9]{64}$'),
    attempt_ready boolean NOT NULL DEFAULT true CHECK (attempt_ready),
    processed_counts jsonb NOT NULL CHECK (jsonb_typeof(processed_counts)='object'),
    classification_counts jsonb NOT NULL CHECK (jsonb_typeof(classification_counts)='object'),
    review_flags jsonb NOT NULL CHECK (
        jsonb_typeof(review_flags)='object'
        AND review_flags = jsonb_build_object(
            'possible_absence',review_flags->'possible_absence',
            'mass_loss',review_flags->'mass_loss',
            'prior_coverage',review_flags->'prior_coverage'
        )
        AND jsonb_typeof(review_flags->'possible_absence')='boolean'
        AND jsonb_typeof(review_flags->'mass_loss')='boolean'
        AND jsonb_typeof(review_flags->'prior_coverage')='boolean'
    ),
    observed_at timestamptz NOT NULL,
    run_sha256 text NOT NULL CHECK (run_sha256 ~ '^[a-f0-9]{64}$'),
    completed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    publishable boolean NOT NULL DEFAULT false CHECK (publishable=false),
    current_read_active boolean NOT NULL DEFAULT false CHECK (current_read_active=false),
    absence_authorized boolean NOT NULL DEFAULT false CHECK (absence_authorized=false),
    requires_review boolean NOT NULL DEFAULT true CHECK (requires_review=true),
    PRIMARY KEY (tenant_id,id),
    UNIQUE (tenant_id,packet_id),
    FOREIGN KEY (
        tenant_id,attempt_id,preparation_id,source_id,attempt_sha256,attempt_ready
    ) REFERENCES public.brain_fileos_v2_later_document_attempts (
        tenant_id,id,preparation_id,source_id,attempt_sha256,ready
    ),
    FOREIGN KEY (
        tenant_id,preparation_id,closure_id,packet_id,baseline_completion_id,
        source_id,root_binding_sha256,preparation_sha256
    ) REFERENCES public.brain_fileos_v2_later_evidence_preparations (
        tenant_id,id,closure_id,packet_id,completion_id,source_id,
        root_binding_sha256,preparation_sha256
    ),
    FOREIGN KEY (tenant_id,closure_id,packet_id,source_id,closure_sha256)
        REFERENCES public.brain_fileos_v2_later_coverage_closures (
            tenant_id,id,packet_id,source_id,closure_sha256
        ),
    FOREIGN KEY (tenant_id,packet_id,baseline_completion_id,source_id,packet_sha256)
        REFERENCES public.brain_fileos_v2_later_observation_packets (
            tenant_id,id,completion_id,source_id,packet_sha256
        )
);

CREATE FUNCTION public.guard_fileos_v2_later_run_completion() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
DECLARE prior_run uuid;
DECLARE latest_run uuid;
DECLARE latest_root text;
DECLARE source_root text;
DECLARE attempt_observed timestamptz;
DECLARE packet_row jsonb;
DECLARE attempt_counts jsonb;
BEGIN
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
        NEW.tenant_id::text || ':fileos-source:' || NEW.source_id,0));
    SELECT a.observed_at,a.counts INTO attempt_observed,attempt_counts
    FROM public.brain_fileos_v2_later_document_attempts a
    WHERE a.tenant_id=NEW.tenant_id AND a.id=NEW.attempt_id
      AND a.preparation_id=NEW.preparation_id AND a.source_id=NEW.source_id
      AND a.attempt_sha256=NEW.attempt_sha256 AND a.ready;
    SELECT p.packet INTO packet_row
    FROM public.brain_fileos_v2_later_observation_packets p
    WHERE p.tenant_id=NEW.tenant_id AND p.id=NEW.packet_id
      AND p.completion_id=NEW.baseline_completion_id
      AND p.source_id=NEW.source_id AND p.packet_sha256=NEW.packet_sha256;
    SELECT prior_run_id INTO prior_run
    FROM public.brain_fileos_v2_baseline_completions
    WHERE tenant_id=NEW.tenant_id AND id=NEW.baseline_completion_id
      AND source_id=NEW.source_id;
    SELECT run_id,root_binding_sha256 INTO latest_run,latest_root
    FROM public.brain_fileos_run_receipts
    WHERE tenant_id=NEW.tenant_id AND source_id=NEW.source_id
    ORDER BY observed_at DESC,completed_at DESC,run_id DESC LIMIT 1;
    SELECT root_binding_sha256 INTO source_root FROM public.brain_sources
    WHERE tenant_id=NEW.tenant_id AND id=NEW.source_id AND kind='fileos';
    IF attempt_observed IS NULL OR NEW.observed_at <= attempt_observed
       OR latest_run IS DISTINCT FROM prior_run
       OR latest_root IS DISTINCT FROM NEW.root_binding_sha256
       OR source_root IS DISTINCT FROM NEW.root_binding_sha256
       OR packet_row IS NULL
       OR packet_row->'candidate'->'counts'->>'errors' IS DISTINCT FROM '0'
       OR NEW.processed_counts IS DISTINCT FROM attempt_counts
       OR NEW.classification_counts IS DISTINCT FROM packet_row->'preview'->'counts'
       OR NEW.review_flags IS DISTINCT FROM pg_catalog.jsonb_build_object(
           'possible_absence',
               (packet_row->'preview'->'counts'->>'absence_candidate')::integer > 0,
           'mass_loss',
               packet_row->'preview'->'blockers' ? 'mass_loss_requires_review',
           'prior_coverage',
               packet_row->'preview'->'blockers' ? 'prior_coverage_requires_review'
       ) THEN
        RAISE EXCEPTION 'invalid FileOS v2 later run completion';
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER fileos_v2_later_run_source_lock
    BEFORE INSERT ON public.brain_fileos_v2_later_run_completions FOR EACH ROW
    EXECUTE FUNCTION public.guard_fileos_v2_later_run_completion();

ALTER TABLE public.brain_fileos_v2_later_run_completions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.brain_fileos_v2_later_run_completions FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON public.brain_fileos_v2_later_run_completions
    USING (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid)
    WITH CHECK (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid);
CREATE POLICY tenant_login_fence ON public.brain_fileos_v2_later_run_completions
    AS RESTRICTIVE FOR ALL TO PUBLIC
    USING (public.masterbrain_tenant_login_allows(tenant_id))
    WITH CHECK (public.masterbrain_tenant_login_allows(tenant_id));
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE
    ON public.brain_fileos_v2_later_run_completions FOR EACH ROW
    EXECUTE FUNCTION public.deny_evidence_mutation();
CREATE TRIGGER protected_no_truncate BEFORE TRUNCATE
    ON public.brain_fileos_v2_later_run_completions FOR EACH STATEMENT
    EXECUTE FUNCTION public.deny_protected_truncate();

COMMIT;
