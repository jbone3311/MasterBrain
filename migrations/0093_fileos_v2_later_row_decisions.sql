BEGIN;

-- Historical human classification decisions. These events cannot activate an
-- index, establish absence, or authorize a source-file effect.
CREATE TABLE public.brain_fileos_v2_later_row_decisions (
    tenant_id uuid NOT NULL,
    reviewer_id uuid NOT NULL,
    idempotency_key uuid NOT NULL,
    source_id text NOT NULL,
    generation_id text NOT NULL,
    run_id uuid NOT NULL,
    run_sha256 text NOT NULL CHECK (run_sha256 ~ '^[a-f0-9]{64}$'),
    closure_id uuid NOT NULL,
    closure_sha256 text NOT NULL CHECK (closure_sha256 ~ '^[a-f0-9]{64}$'),
    locator text NOT NULL CHECK (char_length(locator) BETWEEN 1 AND 4096),
    state text NOT NULL CHECK (state IN (
        'unchanged','changed','deferred_prior','excluded_prior',
        'error_covered_prior','unobserved_prior','absence_candidate',
        'newly_hashed_prior','unobserved_hashless_prior'
    )),
    prior_version_id text,
    disposition text NOT NULL CHECK (disposition IN (
        'investigate','dispute_classification',
        'acknowledge_historical_observation'
    )),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    current_read_active boolean NOT NULL DEFAULT false CHECK (current_read_active=false),
    absence_authorized boolean NOT NULL DEFAULT false CHECK (absence_authorized=false),
    source_effect_authorized boolean NOT NULL DEFAULT false CHECK (source_effect_authorized=false),
    PRIMARY KEY (tenant_id,reviewer_id,idempotency_key),
    FOREIGN KEY (tenant_id,generation_id)
        REFERENCES public.brain_index_generations(tenant_id,id),
    FOREIGN KEY (tenant_id,run_id)
        REFERENCES public.brain_fileos_v2_later_run_completions(tenant_id,id),
    FOREIGN KEY (tenant_id,closure_id)
        REFERENCES public.brain_fileos_v2_later_coverage_closures(tenant_id,id)
);
CREATE INDEX brain_fileos_v2_later_row_decisions_latest
    ON public.brain_fileos_v2_later_row_decisions(
        tenant_id,generation_id,locator,recorded_at DESC,idempotency_key DESC
    );

CREATE FUNCTION public.guard_fileos_v2_later_row_decision() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
DECLARE basis record;
DECLARE prior record;
DECLARE latest record;
DECLARE source_row record;
BEGIN
    IF NEW.reviewer_id IS DISTINCT FROM
       nullif(current_setting('email_brain.actor_id',true),'')::uuid THEN
        RAISE EXCEPTION 'FileOS later row reviewer context mismatch';
    END IF;
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
        NEW.tenant_id::text || ':fileos-source:' || NEW.source_id,0));
    SELECT g.basis_kind,g.v2_later_run_id,g.v2_later_run_sha256,
           r.closure_id,r.root_binding_sha256,r.baseline_completion_id,
           c.closure_sha256,c.closure
      INTO basis
    FROM public.brain_index_generations g
    JOIN public.brain_index_generation_receipts ready
      ON ready.tenant_id=g.tenant_id AND ready.generation_id=g.id
     AND ready.ready_at IS NOT NULL
    JOIN public.brain_fileos_v2_later_run_completions r
      ON r.tenant_id=g.tenant_id AND r.id=g.v2_later_run_id
     AND r.source_id=g.source_id AND r.run_sha256=g.v2_later_run_sha256
    JOIN public.brain_fileos_v2_later_coverage_closures c
      ON c.tenant_id=r.tenant_id AND c.id=r.closure_id
     AND c.source_id=r.source_id
    WHERE g.tenant_id=NEW.tenant_id AND g.id=NEW.generation_id
      AND g.source_id=NEW.source_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'invalid FileOS later row decision basis';
    END IF;
    IF basis.basis_kind IS DISTINCT FROM 'v2_later'
       OR basis.v2_later_run_id IS DISTINCT FROM NEW.run_id
       OR basis.v2_later_run_sha256 IS DISTINCT FROM NEW.run_sha256
       OR basis.closure_id IS DISTINCT FROM NEW.closure_id
       OR basis.closure_sha256 IS DISTINCT FROM NEW.closure_sha256 THEN
        RAISE EXCEPTION 'invalid FileOS later row decision basis';
    END IF;
    SELECT c.prior_run_id,s.prior_actor_id,s.prior_observed_at
      INTO prior
    FROM public.brain_fileos_v2_baseline_completions c
    JOIN public.brain_fileos_v2_staged_inventories s
      ON s.tenant_id=c.tenant_id AND s.id=c.stage_id
    WHERE c.tenant_id=NEW.tenant_id AND c.id=basis.baseline_completion_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'stale FileOS later row decision basis';
    END IF;
    SELECT actor_id,run_id,observed_at,root_binding_sha256 INTO latest
    FROM public.brain_fileos_run_receipts
    WHERE tenant_id=NEW.tenant_id AND source_id=NEW.source_id
    ORDER BY observed_at DESC,completed_at DESC,run_id DESC LIMIT 1;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'stale FileOS later row decision basis';
    END IF;
    SELECT root_binding_sha256,status INTO source_row
    FROM public.brain_sources
    WHERE tenant_id=NEW.tenant_id AND id=NEW.source_id AND kind='fileos';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'stale FileOS later row decision basis';
    END IF;
    IF prior.prior_run_id IS NULL OR latest.actor_id IS DISTINCT FROM prior.prior_actor_id
       OR latest.run_id IS DISTINCT FROM prior.prior_run_id
       OR latest.observed_at IS DISTINCT FROM prior.prior_observed_at
       OR latest.root_binding_sha256 IS DISTINCT FROM basis.root_binding_sha256
       OR source_row.root_binding_sha256 IS DISTINCT FROM basis.root_binding_sha256
       OR source_row.status IS DISTINCT FROM 'active' THEN
        RAISE EXCEPTION 'stale FileOS later row decision basis';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.jsonb_array_elements(basis.closure->'prior_rows')
            AS classified(value)
        WHERE classified.value->>'locator'=NEW.locator
          AND classified.value->>'state'=NEW.state
          AND (classified.value->>'prior_version_id')
              IS NOT DISTINCT FROM NEW.prior_version_id
    ) THEN
        RAISE EXCEPTION 'FileOS later decision row is not in the closure';
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER fileos_v2_later_row_decision_basis
    BEFORE INSERT ON public.brain_fileos_v2_later_row_decisions FOR EACH ROW
    EXECUTE FUNCTION public.guard_fileos_v2_later_row_decision();

ALTER TABLE public.brain_fileos_v2_later_row_decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.brain_fileos_v2_later_row_decisions FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON public.brain_fileos_v2_later_row_decisions
    USING (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid)
    WITH CHECK (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid);
CREATE POLICY tenant_login_fence ON public.brain_fileos_v2_later_row_decisions
    AS RESTRICTIVE FOR ALL TO PUBLIC
    USING (public.masterbrain_tenant_login_allows(tenant_id))
    WITH CHECK (public.masterbrain_tenant_login_allows(tenant_id));
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE
    ON public.brain_fileos_v2_later_row_decisions FOR EACH ROW
    EXECUTE FUNCTION public.deny_evidence_mutation();
CREATE TRIGGER protected_no_truncate BEFORE TRUNCATE
    ON public.brain_fileos_v2_later_row_decisions FOR EACH STATEMENT
    EXECUTE FUNCTION public.deny_protected_truncate();

COMMIT;
