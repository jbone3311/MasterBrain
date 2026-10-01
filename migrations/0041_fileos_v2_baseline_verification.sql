BEGIN;

-- Historical verification of an approved stage; no current-v2 reader or
-- source policy switch consumes this receipt.
ALTER TABLE public.brain_fileos_v2_transition_approvals
    ADD CONSTRAINT brain_fileos_v2_approval_verification_identity UNIQUE (
        tenant_id,id,stage_id,packet_id,source_id,prior_run_id,
        packet_sha256,candidate_sha256,plan_sha256
    );
ALTER TABLE public.brain_fileos_v2_staged_inventories
    ADD CONSTRAINT brain_fileos_v2_stage_verification_identity UNIQUE (
        tenant_id,id,packet_id,source_id,prior_run_id,donor_observed_at,
        packet_sha256,candidate_sha256
    );

CREATE TABLE public.brain_fileos_v2_baseline_verifications (
    tenant_id uuid NOT NULL,
    id uuid NOT NULL,
    actor_id uuid NOT NULL,
    approval_id uuid NOT NULL,
    stage_id uuid NOT NULL,
    packet_id uuid NOT NULL,
    source_id text NOT NULL,
    prior_run_id uuid NOT NULL,
    stage_donor_observed_at timestamptz NOT NULL,
    fresh_observed_at timestamptz NOT NULL,
    packet_sha256 text NOT NULL CHECK (packet_sha256 ~ '^[a-f0-9]{64}$'),
    candidate_sha256 text NOT NULL CHECK (candidate_sha256 ~ '^[a-f0-9]{64}$'),
    plan_sha256 text NOT NULL CHECK (plan_sha256 ~ '^[a-f0-9]{64}$'),
    matched_rows_sha256 text NOT NULL CHECK (matched_rows_sha256 ~ '^[a-f0-9]{64}$'),
    verification_sha256 text NOT NULL CHECK (verification_sha256 ~ '^[a-f0-9]{64}$'),
    verified_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    UNIQUE (tenant_id,source_id),
    UNIQUE (tenant_id,stage_id),
    UNIQUE (tenant_id,approval_id),
    CHECK (fresh_observed_at > stage_donor_observed_at),
    FOREIGN KEY (tenant_id,approval_id,stage_id,packet_id,source_id,prior_run_id,
                 packet_sha256,candidate_sha256,plan_sha256)
        REFERENCES public.brain_fileos_v2_transition_approvals(
            tenant_id,id,stage_id,packet_id,source_id,prior_run_id,
            packet_sha256,candidate_sha256,plan_sha256
        ),
    FOREIGN KEY (tenant_id,stage_id,packet_id,source_id,prior_run_id,
                 stage_donor_observed_at,packet_sha256,candidate_sha256)
        REFERENCES public.brain_fileos_v2_staged_inventories(
            tenant_id,id,packet_id,source_id,prior_run_id,donor_observed_at,
            packet_sha256,candidate_sha256
        )
);
ALTER TABLE public.brain_fileos_v2_baseline_verifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.brain_fileos_v2_baseline_verifications FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON public.brain_fileos_v2_baseline_verifications
    USING (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid)
    WITH CHECK (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid);
CREATE POLICY tenant_login_fence ON public.brain_fileos_v2_baseline_verifications
    AS RESTRICTIVE FOR ALL TO PUBLIC
    USING (public.masterbrain_tenant_login_allows(tenant_id))
    WITH CHECK (public.masterbrain_tenant_login_allows(tenant_id));
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON public.brain_fileos_v2_baseline_verifications
    FOR EACH ROW EXECUTE FUNCTION public.deny_evidence_mutation();
CREATE TRIGGER protected_no_truncate BEFORE TRUNCATE ON public.brain_fileos_v2_baseline_verifications
    FOR EACH STATEMENT EXECUTE FUNCTION public.deny_protected_truncate();

COMMIT;
