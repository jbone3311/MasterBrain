BEGIN;

-- Preparation links hashed stage rows to shared evidence without selecting a
-- current version, completing a v2 run, or changing v1 visibility.
ALTER TABLE public.brain_fileos_v2_baseline_verifications
    ADD CONSTRAINT brain_fileos_v2_verification_preparation_identity UNIQUE (
        tenant_id,id,approval_id,stage_id,source_id,prior_run_id,
        packet_sha256,candidate_sha256,plan_sha256,matched_rows_sha256,
        fresh_observed_at
    );

CREATE TABLE public.brain_fileos_v2_evidence_preparations (
    tenant_id uuid NOT NULL,
    id uuid NOT NULL,
    actor_id uuid NOT NULL,
    verification_id uuid NOT NULL,
    approval_id uuid NOT NULL,
    stage_id uuid NOT NULL,
    source_id text NOT NULL,
    prior_run_id uuid NOT NULL,
    packet_sha256 text NOT NULL CHECK (packet_sha256 ~ '^[a-f0-9]{64}$'),
    candidate_sha256 text NOT NULL CHECK (candidate_sha256 ~ '^[a-f0-9]{64}$'),
    plan_sha256 text NOT NULL CHECK (plan_sha256 ~ '^[a-f0-9]{64}$'),
    matched_rows_sha256 text NOT NULL CHECK (matched_rows_sha256 ~ '^[a-f0-9]{64}$'),
    verification_observed_at timestamptz NOT NULL,
    prepared_observed_at timestamptz NOT NULL,
    hashed_count integer NOT NULL CHECK (hashed_count BETWEEN 0 AND 20000),
    preparation_sha256 text NOT NULL CHECK (preparation_sha256 ~ '^[a-f0-9]{64}$'),
    prepared_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    UNIQUE (tenant_id,source_id),
    UNIQUE (tenant_id,stage_id),
    UNIQUE (tenant_id,verification_id),
    CHECK (prepared_observed_at > verification_observed_at),
    FOREIGN KEY (
        tenant_id,verification_id,approval_id,stage_id,source_id,prior_run_id,
        packet_sha256,candidate_sha256,plan_sha256,matched_rows_sha256,
        verification_observed_at
    ) REFERENCES public.brain_fileos_v2_baseline_verifications (
        tenant_id,id,approval_id,stage_id,source_id,prior_run_id,
        packet_sha256,candidate_sha256,plan_sha256,matched_rows_sha256,
        fresh_observed_at
    )
);

CREATE TABLE public.brain_fileos_v2_prepared_rows (
    tenant_id uuid NOT NULL,
    stage_id uuid NOT NULL,
    source_id text NOT NULL,
    locator text NOT NULL,
    item_id text NOT NULL,
    candidate_version_id text NOT NULL,
    prepared_version_id text NOT NULL,
    evidence_id text NOT NULL,
    PRIMARY KEY (tenant_id,stage_id,locator),
    UNIQUE (tenant_id,stage_id,item_id),
    UNIQUE (tenant_id,stage_id,prepared_version_id),
    FOREIGN KEY (tenant_id,stage_id,locator)
        REFERENCES public.brain_fileos_v2_staged_rows(tenant_id,stage_id,locator),
    FOREIGN KEY (tenant_id,source_id,item_id,prepared_version_id)
        REFERENCES public.brain_source_versions(tenant_id,source_id,item_id,id),
    FOREIGN KEY (tenant_id,evidence_id)
        REFERENCES public.brain_evidence(tenant_id,id)
);

CREATE FUNCTION public.enforce_fileos_v2_prepared_evidence() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
DECLARE actual_count integer;
DECLARE unmatched_count integer;
BEGIN
    SELECT count(*)::integer INTO actual_count
    FROM public.brain_fileos_v2_prepared_rows p
    WHERE p.tenant_id=NEW.tenant_id AND p.stage_id=NEW.stage_id;
    IF actual_count <> NEW.hashed_count THEN
        RAISE EXCEPTION 'invalid FileOS v2 prepared count';
    END IF;
    SELECT count(*)::integer INTO unmatched_count
    FROM public.brain_fileos_v2_staged_rows r
    LEFT JOIN public.brain_fileos_v2_prepared_rows p
      ON p.tenant_id=r.tenant_id AND p.stage_id=r.stage_id
     AND p.locator=r.locator AND p.source_id=r.source_id
     AND p.item_id=r.item_id AND p.candidate_version_id=r.version_id
    LEFT JOIN public.brain_source_items i
      ON i.tenant_id=r.tenant_id AND i.source_id=r.source_id
     AND i.id=r.item_id AND i.locator=r.locator
    LEFT JOIN public.brain_source_versions v
      ON v.tenant_id=r.tenant_id AND v.source_id=r.source_id
     AND v.item_id=r.item_id AND v.id=p.prepared_version_id
     AND v.sha256=r.sha256 AND v.size_bytes=r.size_bytes
     AND v.media_type=r.media_type
    LEFT JOIN public.brain_evidence e
      ON e.tenant_id=r.tenant_id AND e.id=p.evidence_id
     AND e.source_version_id=p.prepared_version_id
     AND e.sha256=r.sha256 AND e.storage='source_bound' AND e.retained=false
    WHERE r.tenant_id=NEW.tenant_id AND r.stage_id=NEW.stage_id
      AND r.kind='hashed' AND (p.locator IS NULL OR i.id IS NULL
                              OR v.id IS NULL OR e.id IS NULL);
    IF unmatched_count <> 0 THEN
        RAISE EXCEPTION 'invalid FileOS v2 prepared evidence';
    END IF;
    RETURN NULL;
END
$function$;
CREATE CONSTRAINT TRIGGER fileos_v2_prepared_evidence
    AFTER INSERT ON public.brain_fileos_v2_evidence_preparations
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION public.enforce_fileos_v2_prepared_evidence();

CREATE FUNCTION public.refuse_late_fileos_v2_prepared_row() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
BEGIN
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
        NEW.tenant_id::text || ':fileos-source:' || NEW.source_id,0));
    IF EXISTS (
        SELECT 1 FROM public.brain_fileos_v2_evidence_preparations
        WHERE tenant_id=NEW.tenant_id AND stage_id=NEW.stage_id
    ) THEN
        RAISE EXCEPTION 'sealed FileOS v2 prepared evidence';
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER fileos_v2_no_late_prepared_row
    BEFORE INSERT ON public.brain_fileos_v2_prepared_rows FOR EACH ROW
    EXECUTE FUNCTION public.refuse_late_fileos_v2_prepared_row();

DO $block$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'brain_fileos_v2_evidence_preparations','brain_fileos_v2_prepared_rows'
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
