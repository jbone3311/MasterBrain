BEGIN;

-- ADR-183: immutable, reviewed entity-to-project role assertions. Roles are
-- descriptive claims, never access grants.
CREATE TABLE public.knowledge_project_members (
    tenant_id uuid NOT NULL,
    id text NOT NULL CHECK (id ~ '^member_[a-f0-9]{32}$'),
    project_id text NOT NULL,
    entity_id text NOT NULL,
    role text NOT NULL CHECK (role ~ '^[a-z][a-z0-9_.-]{0,99}$'),
    assertion_status text NOT NULL CHECK (assertion_status IN ('asserted','disputed','retracted')),
    confidence double precision NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    source_quote text NOT NULL CHECK (length(source_quote) BETWEEN 1 AND 2000),
    observed_at timestamptz NOT NULL,
    valid_from timestamptz,
    valid_to timestamptz,
    supersedes_id text,
    reviewer_id uuid NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    FOREIGN KEY (tenant_id,project_id) REFERENCES public.knowledge_projects(tenant_id,id),
    FOREIGN KEY (tenant_id,entity_id) REFERENCES public.knowledge_entities(tenant_id,id),
    FOREIGN KEY (tenant_id,supersedes_id) REFERENCES public.knowledge_project_members(tenant_id,id),
    CHECK (valid_to IS NULL OR (valid_from IS NOT NULL AND valid_to>valid_from))
);
CREATE INDEX knowledge_project_members_dossier
    ON public.knowledge_project_members(tenant_id,project_id,recorded_at DESC,id DESC);
CREATE INDEX knowledge_project_members_successor
    ON public.knowledge_project_members(tenant_id,supersedes_id)
    WHERE supersedes_id IS NOT NULL;

-- Application validation is not the security boundary: direct runtime SQL
-- cannot attach arbitrary entity types or retarget a supersession chain.
CREATE FUNCTION public.guard_reviewed_project_member() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
DECLARE prior record;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM public.knowledge_entities AS e
        WHERE e.tenant_id=NEW.tenant_id AND e.id=NEW.entity_id
          AND e.entity_type IN ('person','organization')
    ) THEN
        RAISE EXCEPTION 'project member entity must be a person or organization';
    END IF;
    IF NEW.supersedes_id IS NOT NULL THEN
        SELECT m.project_id,m.entity_id INTO prior
        FROM public.knowledge_project_members AS m
        WHERE m.tenant_id=NEW.tenant_id AND m.id=NEW.supersedes_id;
        IF NOT FOUND OR prior.project_id<>NEW.project_id OR prior.entity_id<>NEW.entity_id THEN
            RAISE EXCEPTION 'project member supersession must keep linked identities';
        END IF;
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER reviewed_project_member_guard
    BEFORE INSERT ON public.knowledge_project_members
    FOR EACH ROW EXECUTE FUNCTION public.guard_reviewed_project_member();

ALTER TABLE public.knowledge_corrections DROP CONSTRAINT knowledge_corrections_target_kind_check;
ALTER TABLE public.knowledge_corrections ADD CONSTRAINT knowledge_corrections_target_kind_check
    CHECK (target_kind IN ('entity','relationship','claim','event','project','commitment','member'));
ALTER TABLE public.knowledge_evidence DROP CONSTRAINT knowledge_evidence_target_kind_check;
ALTER TABLE public.knowledge_evidence ADD CONSTRAINT knowledge_evidence_target_kind_check
    CHECK (target_kind IN ('entity','relationship','claim','event','project','commitment','member','correction'));
ALTER TABLE public.knowledge_search_documents DROP CONSTRAINT knowledge_search_documents_object_kind_check;
ALTER TABLE public.knowledge_search_documents ADD CONSTRAINT knowledge_search_documents_object_kind_check
    CHECK (object_kind IN ('entity','relationship','claim','event','project','commitment','member','correction'));

ALTER TABLE public.knowledge_project_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.knowledge_project_members FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON public.knowledge_project_members USING
    (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid)
    WITH CHECK (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid);
CREATE POLICY tenant_login_fence ON public.knowledge_project_members AS RESTRICTIVE
    FOR ALL TO PUBLIC USING (public.masterbrain_tenant_login_allows(tenant_id))
    WITH CHECK (public.masterbrain_tenant_login_allows(tenant_id));
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON public.knowledge_project_members
    FOR EACH ROW EXECUTE FUNCTION public.deny_evidence_mutation();
CREATE TRIGGER protected_no_truncate BEFORE TRUNCATE ON public.knowledge_project_members
    FOR EACH STATEMENT EXECUTE FUNCTION public.deny_protected_truncate();

COMMIT;
