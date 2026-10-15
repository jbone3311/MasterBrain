BEGIN;

-- Historical exact-row closure over one immutable later-observation packet.
-- No current search, freshness, absence or source effect consumes these rows.
ALTER TABLE public.brain_fileos_v2_later_observation_packets
    ADD CONSTRAINT brain_fileos_v2_later_packet_coverage_identity UNIQUE (
        tenant_id,id,completion_id,source_id,packet_sha256,observed_at
    );

CREATE TABLE public.brain_fileos_v2_later_coverage_closures (
    tenant_id uuid NOT NULL,
    id uuid NOT NULL,
    actor_id uuid NOT NULL,
    packet_id uuid NOT NULL,
    completion_id uuid NOT NULL,
    source_id text NOT NULL,
    packet_sha256 text NOT NULL CHECK (packet_sha256 ~ '^[a-f0-9]{64}$'),
    observed_at timestamptz NOT NULL,
    closure_sha256 text NOT NULL CHECK (closure_sha256 ~ '^[a-f0-9]{64}$'),
    closure jsonb NOT NULL CHECK (
        jsonb_typeof(closure) = 'object'
        AND octet_length(closure::text) <= 16777216
        AND closure->>'closure_version' = 'masterbrain-fileos-v2-later-coverage-v1'
        AND closure->>'publishable' = 'false'
        AND closure->>'absence_authorized' = 'false'
        AND closure->>'requires_review' = 'true'
        AND closure->>'packet_sha256' = packet_sha256
        AND closure->>'source_id' = source_id
        AND (closure->>'observed_at')::timestamptz = observed_at
        AND jsonb_typeof(closure->'current_counts') = 'object'
        AND jsonb_typeof(closure->'prior_classification_counts') = 'object'
        AND jsonb_typeof(closure->'current_rows') = 'array'
        AND jsonb_typeof(closure->'prior_rows') = 'array'
        AND jsonb_typeof(closure->'blockers') = 'array'
    ),
    sealed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    UNIQUE (tenant_id,packet_id),
    FOREIGN KEY (
        tenant_id,packet_id,completion_id,source_id,packet_sha256,observed_at
    ) REFERENCES public.brain_fileos_v2_later_observation_packets (
        tenant_id,id,completion_id,source_id,packet_sha256,observed_at
    )
);

ALTER TABLE public.brain_fileos_v2_later_coverage_closures ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.brain_fileos_v2_later_coverage_closures FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON public.brain_fileos_v2_later_coverage_closures
    USING (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid)
    WITH CHECK (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid);
CREATE POLICY tenant_login_fence ON public.brain_fileos_v2_later_coverage_closures
    AS RESTRICTIVE FOR ALL TO PUBLIC
    USING (public.masterbrain_tenant_login_allows(tenant_id))
    WITH CHECK (public.masterbrain_tenant_login_allows(tenant_id));
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE
    ON public.brain_fileos_v2_later_coverage_closures FOR EACH ROW
    EXECUTE FUNCTION public.deny_evidence_mutation();
CREATE TRIGGER protected_no_truncate BEFORE TRUNCATE
    ON public.brain_fileos_v2_later_coverage_closures FOR EACH STATEMENT
    EXECUTE FUNCTION public.deny_protected_truncate();

COMMIT;
