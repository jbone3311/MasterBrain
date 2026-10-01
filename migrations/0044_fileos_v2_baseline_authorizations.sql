BEGIN;

-- Owner authorization is bound to one exact preparation; it does not complete
-- a v2 run or change any v1 current state.
ALTER TABLE public.brain_fileos_v2_evidence_preparations
    ADD CONSTRAINT brain_fileos_v2_preparation_authorization_identity UNIQUE (
        tenant_id,id,approval_id,stage_id,source_id,prior_run_id,
        plan_sha256,preparation_sha256
    );
ALTER TABLE public.brain_fileos_v2_transition_approvals
    ADD CONSTRAINT brain_fileos_v2_approval_authorization_counts UNIQUE (
        tenant_id,id,acknowledged_counts
    );

CREATE TABLE public.brain_fileos_v2_baseline_authorizations (
    tenant_id uuid NOT NULL,
    id uuid NOT NULL,
    actor_id uuid NOT NULL,
    preparation_id uuid NOT NULL,
    approval_id uuid NOT NULL,
    stage_id uuid NOT NULL,
    source_id text NOT NULL,
    prior_run_id uuid NOT NULL,
    plan_sha256 text NOT NULL CHECK (plan_sha256 ~ '^[a-f0-9]{64}$'),
    preparation_sha256 text NOT NULL CHECK (preparation_sha256 ~ '^[a-f0-9]{64}$'),
    acknowledged_counts jsonb NOT NULL CHECK (
        jsonb_typeof(acknowledged_counts) = 'object'
        AND acknowledged_counts ?& ARRAY['candidate_counts','classification_counts']
        AND acknowledged_counts = jsonb_build_object(
            'candidate_counts',acknowledged_counts->'candidate_counts',
            'classification_counts',acknowledged_counts->'classification_counts')
        AND jsonb_typeof(acknowledged_counts->'candidate_counts') = 'object'
        AND jsonb_typeof(acknowledged_counts->'classification_counts') = 'object'
        AND octet_length(acknowledged_counts::text) <= 2000
    ),
    authorized_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    UNIQUE (tenant_id,stage_id),
    UNIQUE (tenant_id,source_id),
    FOREIGN KEY (
        tenant_id,preparation_id,approval_id,stage_id,source_id,prior_run_id,
        plan_sha256,preparation_sha256
    ) REFERENCES public.brain_fileos_v2_evidence_preparations (
        tenant_id,id,approval_id,stage_id,source_id,prior_run_id,
        plan_sha256,preparation_sha256
    ),
    FOREIGN KEY (tenant_id,approval_id,acknowledged_counts)
        REFERENCES public.brain_fileos_v2_transition_approvals (
            tenant_id,id,acknowledged_counts
        )
);

CREATE FUNCTION public.lock_fileos_v2_baseline_authorization() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
DECLARE expected_actor uuid;
DECLARE expected_observed timestamptz;
DECLARE expected_root text;
DECLARE latest_run uuid;
DECLARE latest_actor uuid;
DECLARE latest_observed timestamptz;
DECLARE latest_root text;
DECLARE source_root text;
BEGIN
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
        NEW.tenant_id::text || ':fileos-source:' || NEW.source_id,0));
    SELECT prior_actor_id,prior_observed_at,root_binding_sha256
      INTO expected_actor,expected_observed,expected_root
    FROM public.brain_fileos_v2_staged_inventories
    WHERE tenant_id=NEW.tenant_id AND id=NEW.stage_id
      AND source_id=NEW.source_id AND prior_run_id=NEW.prior_run_id;
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
       OR latest_root IS DISTINCT FROM expected_root
       OR source_root IS DISTINCT FROM expected_root THEN
        RAISE EXCEPTION 'stale FileOS v2 baseline authorization';
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER fileos_v2_authorization_source_lock
    BEFORE INSERT ON public.brain_fileos_v2_baseline_authorizations FOR EACH ROW
    EXECUTE FUNCTION public.lock_fileos_v2_baseline_authorization();

ALTER TABLE public.brain_fileos_v2_baseline_authorizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.brain_fileos_v2_baseline_authorizations FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON public.brain_fileos_v2_baseline_authorizations
    USING (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid)
    WITH CHECK (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid);
CREATE POLICY tenant_login_fence ON public.brain_fileos_v2_baseline_authorizations
    AS RESTRICTIVE FOR ALL TO PUBLIC
    USING (public.masterbrain_tenant_login_allows(tenant_id))
    WITH CHECK (public.masterbrain_tenant_login_allows(tenant_id));
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE
    ON public.brain_fileos_v2_baseline_authorizations FOR EACH ROW
    EXECUTE FUNCTION public.deny_evidence_mutation();
CREATE TRIGGER protected_no_truncate BEFORE TRUNCATE
    ON public.brain_fileos_v2_baseline_authorizations FOR EACH STATEMENT
    EXECUTE FUNCTION public.deny_protected_truncate();

COMMIT;
