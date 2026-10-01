BEGIN;

-- Immutable, private review evidence only. No current-source, freshness,
-- absence, index or publication query reads this table.
CREATE TABLE public.brain_fileos_transition_packets (
    tenant_id uuid NOT NULL,
    id uuid NOT NULL,
    actor_id uuid NOT NULL,
    source_id text NOT NULL,
    prior_actor_id uuid NOT NULL,
    prior_run_id uuid NOT NULL,
    prior_observed_at timestamptz NOT NULL,
    donor_observed_at timestamptz NOT NULL,
    root_binding_sha256 text NOT NULL CHECK (root_binding_sha256 ~ '^[a-f0-9]{64}$'),
    prior_manifest_sha256 text NOT NULL CHECK (prior_manifest_sha256 ~ '^[a-f0-9]{64}$'),
    packet_sha256 text NOT NULL CHECK (packet_sha256 ~ '^[a-f0-9]{64}$'),
    packet jsonb NOT NULL CHECK (
        jsonb_typeof(packet) = 'object'
        AND octet_length(packet::text) <= 16777216
        AND packet->>'packet_version' = 'masterbrain-fileos-transition-review-packet-v1'
        AND packet->>'publishable' = 'false'
        AND packet->>'requires_review' = 'true'
    ),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    UNIQUE (tenant_id,source_id,prior_actor_id,prior_run_id,packet_sha256),
    CHECK (donor_observed_at > prior_observed_at),
    FOREIGN KEY (tenant_id,source_id) REFERENCES public.brain_sources(tenant_id,id),
    FOREIGN KEY (
        tenant_id,prior_actor_id,prior_run_id,source_id,prior_observed_at
    ) REFERENCES public.brain_fileos_run_receipts(
        tenant_id,actor_id,run_id,source_id,observed_at
    )
);
CREATE INDEX brain_fileos_transition_packets_by_source
    ON public.brain_fileos_transition_packets(tenant_id,source_id,recorded_at DESC,id DESC);
ALTER TABLE public.brain_fileos_transition_packets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.brain_fileos_transition_packets FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON public.brain_fileos_transition_packets
    USING (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid)
    WITH CHECK (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid);
CREATE POLICY tenant_login_fence ON public.brain_fileos_transition_packets
    AS RESTRICTIVE FOR ALL TO PUBLIC
    USING (public.masterbrain_tenant_login_allows(tenant_id))
    WITH CHECK (public.masterbrain_tenant_login_allows(tenant_id));
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON public.brain_fileos_transition_packets
    FOR EACH ROW EXECUTE FUNCTION public.deny_evidence_mutation();
CREATE TRIGGER protected_no_truncate BEFORE TRUNCATE ON public.brain_fileos_transition_packets
    FOR EACH STATEMENT EXECUTE FUNCTION public.deny_protected_truncate();

COMMIT;
