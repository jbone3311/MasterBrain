BEGIN;

-- A private completed baseline reuses the immutable staged membership ledger.
-- It cannot become a v1 completion receipt or current-search authority.
ALTER TABLE public.brain_fileos_v2_baseline_authorizations
    ADD CONSTRAINT brain_fileos_v2_authorization_completion_identity UNIQUE (
        tenant_id,id,preparation_id,approval_id,stage_id,source_id,
        prior_run_id,plan_sha256,preparation_sha256,acknowledged_counts
    );
ALTER TABLE public.brain_fileos_v2_evidence_preparations
    ADD CONSTRAINT brain_fileos_v2_preparation_completion_identity UNIQUE (
        tenant_id,id,stage_id,source_id,prior_run_id,plan_sha256,
        matched_rows_sha256,prepared_observed_at,hashed_count
    );
ALTER TABLE public.brain_fileos_v2_staged_inventories
    ADD CONSTRAINT brain_fileos_v2_stage_completion_identity UNIQUE (
        tenant_id,id,source_id,prior_run_id,root_binding_sha256,counts
    );

CREATE TABLE public.brain_fileos_v2_baseline_completions (
    tenant_id uuid NOT NULL,
    id uuid NOT NULL,
    actor_id uuid NOT NULL,
    authorization_id uuid NOT NULL,
    preparation_id uuid NOT NULL,
    approval_id uuid NOT NULL,
    stage_id uuid NOT NULL,
    source_id text NOT NULL,
    prior_run_id uuid NOT NULL,
    root_binding_sha256 text NOT NULL CHECK (root_binding_sha256 ~ '^[a-f0-9]{64}$'),
    plan_sha256 text NOT NULL CHECK (plan_sha256 ~ '^[a-f0-9]{64}$'),
    preparation_sha256 text NOT NULL CHECK (preparation_sha256 ~ '^[a-f0-9]{64}$'),
    matched_rows_sha256 text NOT NULL CHECK (matched_rows_sha256 ~ '^[a-f0-9]{64}$'),
    policy_sha256 text NOT NULL CHECK (policy_sha256 ~ '^[a-f0-9]{64}$'),
    counts jsonb NOT NULL,
    acknowledged_counts jsonb NOT NULL,
    hashed_count integer NOT NULL CHECK (hashed_count BETWEEN 0 AND 20000),
    prepared_observed_at timestamptz NOT NULL,
    fresh_observed_at timestamptz NOT NULL,
    completion_sha256 text NOT NULL CHECK (completion_sha256 ~ '^[a-f0-9]{64}$'),
    completed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    UNIQUE (tenant_id,source_id),
    UNIQUE (tenant_id,stage_id),
    CHECK (fresh_observed_at > prepared_observed_at),
    FOREIGN KEY (
        tenant_id,authorization_id,preparation_id,approval_id,stage_id,
        source_id,prior_run_id,plan_sha256,preparation_sha256,acknowledged_counts
    ) REFERENCES public.brain_fileos_v2_baseline_authorizations (
        tenant_id,id,preparation_id,approval_id,stage_id,source_id,
        prior_run_id,plan_sha256,preparation_sha256,acknowledged_counts
    ),
    FOREIGN KEY (
        tenant_id,preparation_id,stage_id,source_id,prior_run_id,plan_sha256,
        matched_rows_sha256,prepared_observed_at,hashed_count
    ) REFERENCES public.brain_fileos_v2_evidence_preparations (
        tenant_id,id,stage_id,source_id,prior_run_id,plan_sha256,
        matched_rows_sha256,prepared_observed_at,hashed_count
    ),
    FOREIGN KEY (
        tenant_id,stage_id,source_id,prior_run_id,root_binding_sha256,counts
    ) REFERENCES public.brain_fileos_v2_staged_inventories (
        tenant_id,id,source_id,prior_run_id,root_binding_sha256,counts
    )
);

CREATE FUNCTION public.guard_fileos_v2_baseline_completion() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
DECLARE expected_actor uuid;
DECLARE expected_observed timestamptz;
DECLARE latest_actor uuid;
DECLARE latest_run uuid;
DECLARE latest_observed timestamptz;
DECLARE latest_root text;
DECLARE source_root text;
DECLARE staged_counts jsonb;
DECLARE actual_counts jsonb;
DECLARE prepared_count integer;
BEGIN
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
        NEW.tenant_id::text || ':fileos-source:' || NEW.source_id,0));
    SELECT prior_actor_id,prior_observed_at,counts
      INTO expected_actor,expected_observed,staged_counts
    FROM public.brain_fileos_v2_staged_inventories
    WHERE tenant_id=NEW.tenant_id AND id=NEW.stage_id
      AND source_id=NEW.source_id AND prior_run_id=NEW.prior_run_id
      AND root_binding_sha256=NEW.root_binding_sha256;
    SELECT actor_id,run_id,observed_at,root_binding_sha256
      INTO latest_actor,latest_run,latest_observed,latest_root
    FROM public.brain_fileos_run_receipts
    WHERE tenant_id=NEW.tenant_id AND source_id=NEW.source_id
    ORDER BY observed_at DESC,completed_at DESC,run_id DESC LIMIT 1;
    SELECT root_binding_sha256 INTO source_root
    FROM public.brain_sources
    WHERE tenant_id=NEW.tenant_id AND id=NEW.source_id AND kind='fileos';
    IF expected_actor IS NULL OR latest_actor IS DISTINCT FROM expected_actor
       OR latest_run IS DISTINCT FROM NEW.prior_run_id
       OR latest_observed IS DISTINCT FROM expected_observed
       OR latest_root IS DISTINCT FROM NEW.root_binding_sha256
       OR source_root IS DISTINCT FROM NEW.root_binding_sha256 THEN
        RAISE EXCEPTION 'stale FileOS v2 baseline completion';
    END IF;
    IF staged_counts IS DISTINCT FROM NEW.counts
       OR NEW.counts->>'errors' <> '0'
       OR (NEW.counts->>'hashed')::integer <> NEW.hashed_count THEN
        RAISE EXCEPTION 'invalid FileOS v2 baseline counts';
    END IF;
    SELECT pg_catalog.jsonb_build_object(
        'hashed',count(*) FILTER (WHERE kind='hashed'),
        'deferred',count(*) FILTER (WHERE kind='deferred'),
        'excluded',count(*) FILTER (WHERE kind='excluded'),
        'errors',count(*) FILTER (WHERE kind='error'))
    INTO actual_counts FROM public.brain_fileos_v2_staged_rows
    WHERE tenant_id=NEW.tenant_id AND stage_id=NEW.stage_id;
    IF actual_counts IS DISTINCT FROM NEW.counts THEN
        RAISE EXCEPTION 'invalid FileOS v2 baseline ledger';
    END IF;
    SELECT count(*)::integer INTO prepared_count
    FROM public.brain_fileos_v2_prepared_rows
    WHERE tenant_id=NEW.tenant_id AND stage_id=NEW.stage_id;
    IF prepared_count <> NEW.hashed_count THEN
        RAISE EXCEPTION 'invalid FileOS v2 baseline prepared evidence';
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER fileos_v2_completion_source_lock
    BEFORE INSERT ON public.brain_fileos_v2_baseline_completions FOR EACH ROW
    EXECUTE FUNCTION public.guard_fileos_v2_baseline_completion();

ALTER TABLE public.brain_fileos_v2_baseline_completions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.brain_fileos_v2_baseline_completions FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON public.brain_fileos_v2_baseline_completions
    USING (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid)
    WITH CHECK (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid);
CREATE POLICY tenant_login_fence ON public.brain_fileos_v2_baseline_completions
    AS RESTRICTIVE FOR ALL TO PUBLIC
    USING (public.masterbrain_tenant_login_allows(tenant_id))
    WITH CHECK (public.masterbrain_tenant_login_allows(tenant_id));
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE
    ON public.brain_fileos_v2_baseline_completions FOR EACH ROW
    EXECUTE FUNCTION public.deny_evidence_mutation();
CREATE TRIGGER protected_no_truncate BEFORE TRUNCATE
    ON public.brain_fileos_v2_baseline_completions FOR EACH STATEMENT
    EXECUTE FUNCTION public.deny_protected_truncate();

COMMIT;
