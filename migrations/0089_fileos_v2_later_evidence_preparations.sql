BEGIN;

-- Historical source-bound evidence for an exact later coverage closure.
-- No current pointer, completed-run, absence or activation reads this ledger.
ALTER TABLE public.brain_fileos_v2_later_coverage_closures
    ADD CONSTRAINT brain_fileos_v2_later_coverage_preparation_identity UNIQUE (
        tenant_id,id,packet_id,source_id,closure_sha256,observed_at
    );

CREATE TABLE public.brain_fileos_v2_later_evidence_preparations (
    tenant_id uuid NOT NULL,
    id uuid NOT NULL,
    actor_id uuid NOT NULL,
    closure_id uuid NOT NULL,
    packet_id uuid NOT NULL,
    completion_id uuid NOT NULL,
    source_id text NOT NULL,
    root_binding_sha256 text NOT NULL CHECK (root_binding_sha256 ~ '^[a-f0-9]{64}$'),
    packet_sha256 text NOT NULL CHECK (packet_sha256 ~ '^[a-f0-9]{64}$'),
    closure_sha256 text NOT NULL CHECK (closure_sha256 ~ '^[a-f0-9]{64}$'),
    policy_sha256 text NOT NULL CHECK (policy_sha256 ~ '^[a-f0-9]{64}$'),
    matched_rows_sha256 text NOT NULL CHECK (matched_rows_sha256 ~ '^[a-f0-9]{64}$'),
    packet_observed_at timestamptz NOT NULL,
    prepared_observed_at timestamptz NOT NULL
        CHECK (prepared_observed_at > packet_observed_at),
    hashed_count integer NOT NULL CHECK (hashed_count BETWEEN 0 AND 20000),
    preparation_sha256 text NOT NULL CHECK (preparation_sha256 ~ '^[a-f0-9]{64}$'),
    prepared_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    UNIQUE (tenant_id,closure_id),
    FOREIGN KEY (
        tenant_id,closure_id,packet_id,source_id,closure_sha256,packet_observed_at
    ) REFERENCES public.brain_fileos_v2_later_coverage_closures (
        tenant_id,id,packet_id,source_id,closure_sha256,observed_at
    ),
    FOREIGN KEY (
        tenant_id,packet_id,completion_id,source_id,packet_sha256,packet_observed_at
    ) REFERENCES public.brain_fileos_v2_later_observation_packets (
        tenant_id,id,completion_id,source_id,packet_sha256,observed_at
    )
);

CREATE TABLE public.brain_fileos_v2_later_prepared_rows (
    tenant_id uuid NOT NULL,
    preparation_id uuid NOT NULL,
    source_id text NOT NULL,
    locator text NOT NULL CHECK (length(locator) BETWEEN 1 AND 4000),
    item_id text NOT NULL,
    candidate_version_id text NOT NULL,
    prepared_version_id text NOT NULL,
    evidence_id text NOT NULL,
    sha256 text NOT NULL CHECK (sha256 ~ '^[a-f0-9]{64}$'),
    size_bytes bigint NOT NULL CHECK (size_bytes >= 0),
    media_type text NOT NULL CHECK (length(media_type) BETWEEN 1 AND 200),
    PRIMARY KEY (tenant_id,preparation_id,locator),
    FOREIGN KEY (tenant_id,preparation_id)
        REFERENCES public.brain_fileos_v2_later_evidence_preparations(tenant_id,id)
        DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY (tenant_id,source_id,item_id,prepared_version_id)
        REFERENCES public.brain_source_versions(tenant_id,source_id,item_id,id),
    FOREIGN KEY (tenant_id,evidence_id)
        REFERENCES public.brain_evidence(tenant_id,id)
);

CREATE FUNCTION public.guard_fileos_v2_later_evidence_preparation() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
DECLARE prior_run uuid;
DECLARE latest_run uuid;
DECLARE latest_root text;
DECLARE source_root text;
DECLARE packet_root text;
BEGIN
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
        NEW.tenant_id::text || ':fileos-source:' || NEW.source_id,0));
    SELECT prior_run_id INTO prior_run
    FROM public.brain_fileos_v2_baseline_completions
    WHERE tenant_id=NEW.tenant_id AND id=NEW.completion_id
      AND source_id=NEW.source_id;
    SELECT root_binding_sha256 INTO packet_root
    FROM public.brain_fileos_v2_later_observation_packets
    WHERE tenant_id=NEW.tenant_id AND id=NEW.packet_id
      AND completion_id=NEW.completion_id AND source_id=NEW.source_id;
    SELECT run_id,root_binding_sha256 INTO latest_run,latest_root
    FROM public.brain_fileos_run_receipts
    WHERE tenant_id=NEW.tenant_id AND source_id=NEW.source_id
    ORDER BY observed_at DESC,completed_at DESC,run_id DESC LIMIT 1;
    SELECT root_binding_sha256 INTO source_root FROM public.brain_sources
    WHERE tenant_id=NEW.tenant_id AND id=NEW.source_id AND kind='fileos';
    IF prior_run IS NULL OR latest_run IS DISTINCT FROM prior_run
       OR packet_root IS DISTINCT FROM NEW.root_binding_sha256
       OR latest_root IS DISTINCT FROM NEW.root_binding_sha256
       OR source_root IS DISTINCT FROM NEW.root_binding_sha256 THEN
        RAISE EXCEPTION 'stale FileOS v2 later evidence preparation';
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER fileos_v2_later_evidence_source_lock
    BEFORE INSERT ON public.brain_fileos_v2_later_evidence_preparations FOR EACH ROW
    EXECUTE FUNCTION public.guard_fileos_v2_later_evidence_preparation();

CREATE FUNCTION public.enforce_fileos_v2_later_prepared_rows() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
DECLARE saved_closure jsonb;
DECLARE actual_count integer;
DECLARE missing_count integer;
BEGIN
    SELECT closure INTO saved_closure
    FROM public.brain_fileos_v2_later_coverage_closures
    WHERE tenant_id=NEW.tenant_id AND id=NEW.closure_id;
    SELECT count(*)::integer INTO actual_count
    FROM public.brain_fileos_v2_later_prepared_rows
    WHERE tenant_id=NEW.tenant_id AND preparation_id=NEW.id;
    IF saved_closure IS NULL OR NEW.hashed_count <> (saved_closure->'current_counts'->>'hashed')::integer
       OR actual_count <> NEW.hashed_count THEN
        RAISE EXCEPTION 'invalid FileOS v2 later prepared row count';
    END IF;
    SELECT count(*)::integer INTO missing_count
    FROM pg_catalog.jsonb_to_recordset(saved_closure->'current_rows') AS c(
        kind text, locator text, item_id text, candidate_version_id text,
        sha256 text, size_bytes bigint, media_type text
    )
    LEFT JOIN public.brain_fileos_v2_later_prepared_rows r
      ON r.tenant_id=NEW.tenant_id AND r.preparation_id=NEW.id
     AND r.locator=c.locator AND r.item_id=c.item_id
     AND r.candidate_version_id=c.candidate_version_id AND r.sha256=c.sha256
     AND r.size_bytes=c.size_bytes AND r.media_type=c.media_type
    LEFT JOIN public.brain_source_versions v
      ON v.tenant_id=r.tenant_id AND v.id=r.prepared_version_id
     AND v.source_id=NEW.source_id AND v.item_id=r.item_id
     AND v.sha256=r.sha256 AND v.size_bytes=r.size_bytes
     AND v.media_type=r.media_type
     AND v.metadata->>'candidate_version_id'=r.candidate_version_id
     AND v.metadata->>'inventory_policy_sha256'=NEW.policy_sha256
    LEFT JOIN public.brain_evidence e
      ON e.tenant_id=r.tenant_id AND e.id=r.evidence_id
     AND e.source_version_id=r.prepared_version_id AND e.sha256=r.sha256
     AND e.storage='source_bound' AND e.retained=false
    WHERE c.kind='hashed' AND (r.locator IS NULL OR v.id IS NULL OR e.id IS NULL);
    IF missing_count <> 0 THEN
        RAISE EXCEPTION 'incomplete FileOS v2 later prepared rows';
    END IF;
    RETURN NULL;
END
$function$;
CREATE CONSTRAINT TRIGGER fileos_v2_later_prepared_rows_complete
    AFTER INSERT ON public.brain_fileos_v2_later_evidence_preparations
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION public.enforce_fileos_v2_later_prepared_rows();

CREATE FUNCTION public.refuse_late_fileos_v2_later_prepared_row() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
BEGIN
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
        NEW.tenant_id::text || ':fileos-source:' || NEW.source_id,0));
    IF EXISTS (SELECT 1 FROM public.brain_fileos_v2_later_evidence_preparations
               WHERE tenant_id=NEW.tenant_id AND id=NEW.preparation_id) THEN
        RAISE EXCEPTION 'sealed FileOS v2 later evidence preparation';
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER fileos_v2_later_prepared_row_closed
    BEFORE INSERT ON public.brain_fileos_v2_later_prepared_rows FOR EACH ROW
    EXECUTE FUNCTION public.refuse_late_fileos_v2_later_prepared_row();

DO $block$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'brain_fileos_v2_later_evidence_preparations',
        'brain_fileos_v2_later_prepared_rows'
    ] LOOP
        EXECUTE pg_catalog.format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',table_name);
        EXECUTE pg_catalog.format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY',table_name);
        EXECUTE pg_catalog.format(
            'CREATE POLICY tenant_isolation ON public.%I USING '
            || '(tenant_id=nullif(current_setting(''email_brain.tenant_id'',true),'''')::uuid) '
            || 'WITH CHECK (tenant_id=nullif(current_setting(''email_brain.tenant_id'',true),'''')::uuid)',
            table_name
        );
        EXECUTE pg_catalog.format(
            'CREATE POLICY tenant_login_fence ON public.%I AS RESTRICTIVE FOR ALL TO PUBLIC '
            || 'USING (public.masterbrain_tenant_login_allows(tenant_id)) '
            || 'WITH CHECK (public.masterbrain_tenant_login_allows(tenant_id))',table_name
        );
        EXECUTE pg_catalog.format(
            'CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON public.%I FOR EACH ROW '
            || 'EXECUTE FUNCTION public.deny_evidence_mutation()',table_name
        );
        EXECUTE pg_catalog.format(
            'CREATE TRIGGER protected_no_truncate BEFORE TRUNCATE ON public.%I FOR EACH STATEMENT '
            || 'EXECUTE FUNCTION public.deny_protected_truncate()',table_name
        );
    END LOOP;
END
$block$;

COMMIT;
