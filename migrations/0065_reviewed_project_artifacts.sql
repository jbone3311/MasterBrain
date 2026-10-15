BEGIN;

-- ADR-193: reviewed links to exact evidence occurrences, never hashes or paths.
CREATE TABLE public.knowledge_project_artifacts (
    tenant_id uuid NOT NULL,
    id text NOT NULL CHECK (id ~ '^partifact_[a-f0-9]{32}$'),
    project_id text NOT NULL,
    artifact_evidence_id text NOT NULL,
    basis_evidence_id text NOT NULL,
    relation text NOT NULL CHECK (relation ~ '^[a-z][a-z0-9_.-]{0,99}$'),
    assertion_status text NOT NULL CHECK (assertion_status IN ('asserted','retracted')),
    source_quote text NOT NULL CHECK (length(source_quote) BETWEEN 1 AND 2000),
    observed_at timestamptz NOT NULL,
    reviewer_id uuid NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    FOREIGN KEY (tenant_id,project_id)
        REFERENCES public.knowledge_projects(tenant_id,id),
    FOREIGN KEY (tenant_id,artifact_evidence_id)
        REFERENCES public.brain_evidence(tenant_id,id),
    FOREIGN KEY (tenant_id,basis_evidence_id)
        REFERENCES public.brain_evidence(tenant_id,id)
);
CREATE INDEX knowledge_project_artifacts_page
    ON public.knowledge_project_artifacts(tenant_id,project_id,recorded_at DESC,id DESC);

-- The SQL boundary also refuses a forged link to stale/excluded evidence or
-- an invented quote, even if the caller bypasses application validation.
CREATE FUNCTION public.guard_project_artifact_basis() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM public.brain_evidence e
        JOIN public.brain_source_versions v
          ON v.tenant_id=e.tenant_id AND v.id=e.source_version_id
        JOIN public.brain_source_items i
          ON i.tenant_id=v.tenant_id AND i.id=v.item_id AND i.source_id=v.source_id
        JOIN public.brain_sources s
          ON s.tenant_id=i.tenant_id AND s.id=i.source_id
        WHERE e.tenant_id=NEW.tenant_id AND e.id=NEW.artifact_evidence_id
          AND i.current_version_id=v.id AND s.status='active'
          AND NOT public.brain_email_evidence_is_excluded(e.tenant_id,e.id)
    ) OR NOT EXISTS (
        SELECT 1 FROM public.brain_evidence e
        JOIN public.brain_source_versions v
          ON v.tenant_id=e.tenant_id AND v.id=e.source_version_id
        JOIN public.brain_source_items i
          ON i.tenant_id=v.tenant_id AND i.id=v.item_id AND i.source_id=v.source_id
        JOIN public.brain_sources s
          ON s.tenant_id=i.tenant_id AND s.id=i.source_id
        JOIN public.brain_normalized_documents d
          ON d.tenant_id=e.tenant_id AND d.evidence_id=e.id
        WHERE e.tenant_id=NEW.tenant_id AND e.id=NEW.basis_evidence_id
          AND i.current_version_id=v.id AND s.status='active'
          AND NOT public.brain_email_evidence_is_excluded(e.tenant_id,e.id)
          AND position(NEW.source_quote IN d.body)>0
    ) THEN
        RAISE EXCEPTION 'invalid project artifact basis';
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER project_artifact_basis
    BEFORE INSERT ON public.knowledge_project_artifacts
    FOR EACH ROW EXECUTE FUNCTION public.guard_project_artifact_basis();

CREATE TABLE public.knowledge_project_artifact_receipts (
    tenant_id uuid NOT NULL,
    actor_id uuid NOT NULL,
    idempotency_key uuid NOT NULL,
    request_sha256 text NOT NULL CHECK (request_sha256 ~ '^[a-f0-9]{64}$'),
    link_id text NOT NULL,
    PRIMARY KEY (tenant_id,actor_id,idempotency_key),
    FOREIGN KEY (tenant_id,link_id)
        REFERENCES public.knowledge_project_artifacts(tenant_id,id)
);

DO $block$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'knowledge_project_artifacts','knowledge_project_artifact_receipts'
    ] LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',table_name);
        EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY',table_name);
        EXECUTE format('CREATE POLICY tenant_isolation ON public.%I USING
            (tenant_id=nullif(current_setting(''email_brain.tenant_id'',true),'''')::uuid)
            WITH CHECK (tenant_id=nullif(current_setting(''email_brain.tenant_id'',true),'''')::uuid)',table_name);
        EXECUTE format('CREATE POLICY tenant_login_fence ON public.%I AS RESTRICTIVE
            FOR ALL TO PUBLIC USING (public.masterbrain_tenant_login_allows(tenant_id))
            WITH CHECK (public.masterbrain_tenant_login_allows(tenant_id))',table_name);
        EXECUTE format('CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON public.%I
            FOR EACH ROW EXECUTE FUNCTION public.deny_evidence_mutation()',table_name);
        EXECUTE format('CREATE TRIGGER protected_no_truncate BEFORE TRUNCATE ON public.%I
            FOR EACH STATEMENT EXECUTE FUNCTION public.deny_protected_truncate()',table_name);
    END LOOP;
END $block$;

COMMIT;
