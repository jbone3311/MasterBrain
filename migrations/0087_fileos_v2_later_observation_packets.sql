BEGIN;

-- Historical review packets only; no freshness, absence, active-index or
-- current-search view reads this table.
ALTER TABLE public.brain_fileos_v2_baseline_completions
    ADD CONSTRAINT brain_fileos_v2_completion_packet_identity UNIQUE (
        tenant_id,id,source_id,root_binding_sha256,completion_sha256
    );

CREATE TABLE public.brain_fileos_v2_later_observation_packets (
    tenant_id uuid NOT NULL,
    id uuid NOT NULL,
    actor_id uuid NOT NULL,
    completion_id uuid NOT NULL,
    source_id text NOT NULL,
    root_binding_sha256 text NOT NULL CHECK (root_binding_sha256 ~ '^[a-f0-9]{64}$'),
    baseline_completion_sha256 text NOT NULL
        CHECK (baseline_completion_sha256 ~ '^[a-f0-9]{64}$'),
    observed_at timestamptz NOT NULL,
    packet_sha256 text NOT NULL CHECK (packet_sha256 ~ '^[a-f0-9]{64}$'),
    packet jsonb NOT NULL CHECK (
        jsonb_typeof(packet) = 'object'
        AND octet_length(packet::text) <= 16777216
        AND packet->>'packet_version' = 'masterbrain-fileos-v2-later-observation-packet-v1'
        AND packet->>'publishable' = 'false'
        AND packet->>'absence_authorized' = 'false'
        AND packet->>'requires_review' = 'true'
        AND packet->>'completion_id' = completion_id::text
        AND packet->>'source_id' = source_id
        AND packet->>'root_binding_sha256' = root_binding_sha256
        AND packet->>'baseline_completion_sha256' = baseline_completion_sha256
        AND jsonb_typeof(packet->'candidate') = 'object'
        AND jsonb_typeof(packet->'preview') = 'object'
        AND packet->'candidate'->'root_binding'->>'sha256' = root_binding_sha256
        AND packet->'candidate'->'source'->>'source_id' = source_id
        AND (packet->'candidate'->>'observed_at')::timestamptz = observed_at
    ),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    FOREIGN KEY (
        tenant_id,completion_id,source_id,root_binding_sha256,
        baseline_completion_sha256
    ) REFERENCES public.brain_fileos_v2_baseline_completions (
        tenant_id,id,source_id,root_binding_sha256,completion_sha256
    )
);

CREATE INDEX brain_fileos_v2_later_packets_by_source
    ON public.brain_fileos_v2_later_observation_packets
    (tenant_id,source_id,observed_at DESC,id DESC);

CREATE FUNCTION public.guard_fileos_v2_later_packet() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
DECLARE baseline_observed timestamptz;
DECLARE prior_run uuid;
DECLARE latest_run uuid;
DECLARE latest_root text;
DECLARE source_root text;
BEGIN
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
        NEW.tenant_id::text || ':fileos-source:' || NEW.source_id,0));
    SELECT fresh_observed_at,prior_run_id
      INTO baseline_observed,prior_run
    FROM public.brain_fileos_v2_baseline_completions
    WHERE tenant_id=NEW.tenant_id AND id=NEW.completion_id
      AND source_id=NEW.source_id
      AND root_binding_sha256=NEW.root_binding_sha256
      AND completion_sha256=NEW.baseline_completion_sha256;
    SELECT run_id,root_binding_sha256 INTO latest_run,latest_root
    FROM public.brain_fileos_run_receipts
    WHERE tenant_id=NEW.tenant_id AND source_id=NEW.source_id
    ORDER BY observed_at DESC,completed_at DESC,run_id DESC LIMIT 1;
    SELECT root_binding_sha256 INTO source_root FROM public.brain_sources
    WHERE tenant_id=NEW.tenant_id AND id=NEW.source_id AND kind='fileos';
    IF baseline_observed IS NULL OR NEW.observed_at <= baseline_observed
       OR latest_run IS DISTINCT FROM prior_run
       OR latest_root IS DISTINCT FROM NEW.root_binding_sha256
       OR source_root IS DISTINCT FROM NEW.root_binding_sha256 THEN
        RAISE EXCEPTION 'stale FileOS v2 later observation packet';
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER fileos_v2_later_packet_source_lock
    BEFORE INSERT ON public.brain_fileos_v2_later_observation_packets FOR EACH ROW
    EXECUTE FUNCTION public.guard_fileos_v2_later_packet();

ALTER TABLE public.brain_fileos_v2_later_observation_packets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.brain_fileos_v2_later_observation_packets FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON public.brain_fileos_v2_later_observation_packets
    USING (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid)
    WITH CHECK (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid);
CREATE POLICY tenant_login_fence ON public.brain_fileos_v2_later_observation_packets
    AS RESTRICTIVE FOR ALL TO PUBLIC
    USING (public.masterbrain_tenant_login_allows(tenant_id))
    WITH CHECK (public.masterbrain_tenant_login_allows(tenant_id));
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE
    ON public.brain_fileos_v2_later_observation_packets FOR EACH ROW
    EXECUTE FUNCTION public.deny_evidence_mutation();
CREATE TRIGGER protected_no_truncate BEFORE TRUNCATE
    ON public.brain_fileos_v2_later_observation_packets FOR EACH STATEMENT
    EXECUTE FUNCTION public.deny_protected_truncate();

COMMIT;
