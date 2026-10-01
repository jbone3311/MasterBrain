BEGIN;

-- Staging is deliberately outside all v1 freshness, absence and search views.
ALTER TABLE public.brain_fileos_transition_packets
    ADD CONSTRAINT brain_fileos_transition_stage_identity UNIQUE (
        tenant_id,id,source_id,prior_actor_id,prior_run_id,prior_observed_at,
        donor_observed_at,root_binding_sha256,packet_sha256
    );
CREATE TABLE public.brain_fileos_v2_staged_inventories (
    tenant_id uuid NOT NULL,
    id uuid NOT NULL,
    actor_id uuid NOT NULL,
    packet_id uuid NOT NULL,
    source_id text NOT NULL,
    prior_actor_id uuid NOT NULL,
    prior_run_id uuid NOT NULL,
    prior_observed_at timestamptz NOT NULL,
    donor_observed_at timestamptz NOT NULL,
    root_binding_sha256 text NOT NULL CHECK (root_binding_sha256 ~ '^[a-f0-9]{64}$'),
    packet_sha256 text NOT NULL CHECK (packet_sha256 ~ '^[a-f0-9]{64}$'),
    candidate_sha256 text NOT NULL CHECK (candidate_sha256 ~ '^[a-f0-9]{64}$'),
    counts jsonb NOT NULL CHECK (
        jsonb_typeof(counts) = 'object'
        AND counts ?& ARRAY['hashed','deferred','excluded','errors']
        AND counts = jsonb_build_object(
            'hashed',counts->'hashed','deferred',counts->'deferred',
            'excluded',counts->'excluded','errors',counts->'errors')
        AND (counts->>'hashed') ~ '^(0|[1-9][0-9]*)$'
        AND (counts->>'deferred') ~ '^(0|[1-9][0-9]*)$'
        AND (counts->>'excluded') ~ '^(0|[1-9][0-9]*)$'
        AND (counts->>'errors') ~ '^(0|[1-9][0-9]*)$'
        AND jsonb_typeof(counts->'hashed') = 'number'
        AND jsonb_typeof(counts->'deferred') = 'number'
        AND jsonb_typeof(counts->'excluded') = 'number'
        AND jsonb_typeof(counts->'errors') = 'number'
        AND (counts->>'hashed')::integer <= 20000
        AND (counts->>'deferred')::integer <= 20000
        AND (counts->>'excluded')::integer <= 20000
        AND (counts->>'errors')::integer <= 20000
        AND (counts->>'hashed')::integer + (counts->>'deferred')::integer
            + (counts->>'excluded')::integer + (counts->>'errors')::integer <= 20000
    ),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    UNIQUE (tenant_id,packet_id),
    UNIQUE (tenant_id,id,source_id),
    CHECK (donor_observed_at > prior_observed_at),
    FOREIGN KEY (tenant_id,packet_id,source_id,prior_actor_id,prior_run_id,
                 prior_observed_at,donor_observed_at,root_binding_sha256,packet_sha256)
        REFERENCES public.brain_fileos_transition_packets(
            tenant_id,id,source_id,prior_actor_id,prior_run_id,prior_observed_at,
            donor_observed_at,root_binding_sha256,packet_sha256
        ),
    FOREIGN KEY (tenant_id,prior_actor_id,prior_run_id,source_id,prior_observed_at)
        REFERENCES public.brain_fileos_run_receipts(
            tenant_id,actor_id,run_id,source_id,observed_at
        )
);

CREATE TABLE public.brain_fileos_v2_staged_rows (
    tenant_id uuid NOT NULL,
    stage_id uuid NOT NULL,
    source_id text NOT NULL,
    kind text NOT NULL CHECK (kind IN ('hashed','deferred','excluded','error')),
    locator text NOT NULL CHECK (length(locator) BETWEEN 1 AND 4000),
    item_id text,
    version_id text,
    sha256 text,
    size_bytes bigint,
    media_type text,
    reason text,
    PRIMARY KEY (tenant_id,stage_id,locator),
    FOREIGN KEY (tenant_id,stage_id,source_id)
        REFERENCES public.brain_fileos_v2_staged_inventories(tenant_id,id,source_id),
    CHECK (
        (kind = 'hashed' AND item_id ~ '^[a-z][a-z0-9_-]{0,127}$'
         AND version_id ~ '^[a-z][a-z0-9_-]{0,127}$'
         AND sha256 ~ '^[a-f0-9]{64}$' AND size_bytes BETWEEN 0 AND 2147483648
         AND length(media_type) BETWEEN 1 AND 200 AND reason IS NULL)
        OR (kind = 'deferred' AND item_id ~ '^[a-z][a-z0-9_-]{0,127}$'
            AND version_id IS NULL AND sha256 IS NULL AND size_bytes >= 0
            AND media_type IS NULL AND reason IN ('no_hash','dataless','oversize'))
        OR (kind = 'excluded' AND item_id IS NULL AND version_id IS NULL
            AND sha256 IS NULL AND size_bytes IS NULL AND media_type IS NULL
            AND reason IN ('donor_junk_dir','donor_operational_dir','donor_junk_file',
                           'symlink_directory','not_regular'))
        OR (kind = 'error' AND item_id IS NULL AND version_id IS NULL
            AND sha256 IS NULL AND size_bytes IS NULL AND media_type IS NULL
            AND reason IN ('directory_unreadable','root_changed_during_scan',
                           'symlink_skipped','changed_during_scan','file_unreadable'))
    )
);

CREATE FUNCTION public.enforce_fileos_v2_staged_ledger() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
DECLARE expected jsonb;
DECLARE actual jsonb;
DECLARE stage_uuid uuid;
BEGIN
    stage_uuid := COALESCE((to_jsonb(NEW)->>'stage_id')::uuid,(to_jsonb(NEW)->>'id')::uuid);
    SELECT counts INTO expected FROM public.brain_fileos_v2_staged_inventories
    WHERE tenant_id=NEW.tenant_id AND id=stage_uuid;
    SELECT pg_catalog.jsonb_build_object(
        'hashed',count(*) FILTER (WHERE kind='hashed'),
        'deferred',count(*) FILTER (WHERE kind='deferred'),
        'excluded',count(*) FILTER (WHERE kind='excluded'),
        'errors',count(*) FILTER (WHERE kind='error'))
    INTO actual FROM public.brain_fileos_v2_staged_rows
    WHERE tenant_id=NEW.tenant_id AND stage_id=stage_uuid;
    IF expected IS NULL OR actual <> expected THEN
        RAISE EXCEPTION 'invalid FileOS v2 staged ledger';
    END IF;
    RETURN NULL;
END
$function$;
CREATE CONSTRAINT TRIGGER fileos_v2_stage_ledger
    AFTER INSERT ON public.brain_fileos_v2_staged_inventories
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION public.enforce_fileos_v2_staged_ledger();
CREATE CONSTRAINT TRIGGER fileos_v2_row_ledger
    AFTER INSERT ON public.brain_fileos_v2_staged_rows
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION public.enforce_fileos_v2_staged_ledger();

DO $block$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'brain_fileos_v2_staged_inventories','brain_fileos_v2_staged_rows'
    ] LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',table_name);
        EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY',table_name);
        EXECUTE format('CREATE POLICY tenant_isolation ON public.%I USING '
            || '(tenant_id=nullif(current_setting(''email_brain.tenant_id'',true),'''')::uuid) '
            || 'WITH CHECK (tenant_id=nullif(current_setting(''email_brain.tenant_id'',true),'''')::uuid)',table_name);
        EXECUTE format('CREATE POLICY tenant_login_fence ON public.%I AS RESTRICTIVE '
            || 'FOR ALL TO PUBLIC USING (public.masterbrain_tenant_login_allows(tenant_id)) '
            || 'WITH CHECK (public.masterbrain_tenant_login_allows(tenant_id))',table_name);
        EXECUTE format('CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON public.%I '
            || 'FOR EACH ROW EXECUTE FUNCTION public.deny_evidence_mutation()',table_name);
        EXECUTE format('CREATE TRIGGER protected_no_truncate BEFORE TRUNCATE ON public.%I '
            || 'FOR EACH STATEMENT EXECUTE FUNCTION public.deny_protected_truncate()',table_name);
    END LOOP;
END $block$;

COMMIT;
