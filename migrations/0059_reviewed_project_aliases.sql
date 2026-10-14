BEGIN;

-- ADR-182: additive reviewed project aliases. The canonical title is inserted
-- as a title-kind row for newly reviewed projects; historical projects remain
-- unchanged and still have exact-title fallback in the resolver.
ALTER TABLE public.knowledge_projects ADD COLUMN alias_manifest_sha256 text
    CHECK (alias_manifest_sha256 IS NULL OR alias_manifest_sha256 ~ '^[a-f0-9]{64}$');

CREATE TABLE public.knowledge_project_aliases (
    tenant_id uuid NOT NULL,
    id text NOT NULL CHECK (id ~ '^palias_[a-f0-9]{32}$'),
    project_id text NOT NULL,
    alias text NOT NULL CHECK (length(alias) BETWEEN 1 AND 300),
    normalized_alias text NOT NULL CHECK (length(normalized_alias) BETWEEN 1 AND 300),
    alias_kind text NOT NULL CHECK (alias_kind IN
        ('title','name','address','legal_entity','folder','other')),
    evidence_id text NOT NULL,
    source_quote text NOT NULL CHECK (length(source_quote) BETWEEN 1 AND 2000),
    reviewer_id uuid NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    UNIQUE (tenant_id,project_id,normalized_alias),
    FOREIGN KEY (tenant_id,project_id)
        REFERENCES public.knowledge_projects(tenant_id,id),
    FOREIGN KEY (tenant_id,evidence_id)
        REFERENCES public.brain_evidence(tenant_id,id)
);
CREATE INDEX knowledge_project_aliases_lookup
    ON public.knowledge_project_aliases(tenant_id,normalized_alias,project_id);

CREATE FUNCTION public.project_alias_manifest(
    project_tenant uuid, reviewed_project text
) RETURNS text LANGUAGE sql STABLE SET search_path=pg_catalog AS $function$
    SELECT pg_catalog.encode(public.digest(coalesce(pg_catalog.string_agg(
        pg_catalog.char_length(a.normalized_alias)::text || ':' || a.normalized_alias ||
        pg_catalog.char_length(a.alias_kind)::text || ':' || a.alias_kind ||
        pg_catalog.char_length(a.evidence_id)::text || ':' || a.evidence_id ||
        pg_catalog.char_length(a.source_quote)::text || ':' || a.source_quote,
        '' ORDER BY a.normalized_alias COLLATE "C"), ''), 'sha256'), 'hex')
    FROM public.knowledge_project_aliases AS a
    WHERE a.tenant_id=project_tenant AND a.project_id=reviewed_project
$function$;

CREATE FUNCTION public.guard_project_alias_manifest() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
BEGIN
    IF NEW.alias_manifest_sha256 IS NOT NULL AND
       public.project_alias_manifest(NEW.tenant_id,NEW.id)
           IS DISTINCT FROM NEW.alias_manifest_sha256 THEN
        RAISE EXCEPTION 'reviewed project alias set differs';
    END IF;
    RETURN NULL;
END
$function$;
CREATE CONSTRAINT TRIGGER project_alias_manifest_complete
    AFTER INSERT ON public.knowledge_projects
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION public.guard_project_alias_manifest();

-- The project and its evidence links are written in one reviewed transaction.
-- Check at commit so an alias cannot cite an unrelated evidence item or spoof
-- a different project reviewer through direct SQL.
CREATE FUNCTION public.guard_reviewed_project_alias() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM public.knowledge_projects AS p
        JOIN public.knowledge_evidence AS ke ON ke.tenant_id=p.tenant_id
          AND ke.target_kind='project' AND ke.target_id=p.id
        WHERE p.tenant_id=NEW.tenant_id AND p.id=NEW.project_id
          AND p.alias_manifest_sha256 IS NOT NULL
          AND p.reviewer_id=NEW.reviewer_id
          AND ke.evidence_id=NEW.evidence_id AND ke.stance='supports'
    ) THEN
        RAISE EXCEPTION 'invalid reviewed project alias basis';
    END IF;
    IF public.project_alias_manifest(NEW.tenant_id,NEW.project_id) IS DISTINCT FROM
       (SELECT p.alias_manifest_sha256 FROM public.knowledge_projects AS p
        WHERE p.tenant_id=NEW.tenant_id AND p.id=NEW.project_id) THEN
        RAISE EXCEPTION 'reviewed project alias set differs';
    END IF;
    RETURN NULL;
END
$function$;
CREATE CONSTRAINT TRIGGER reviewed_project_alias_basis
    AFTER INSERT ON public.knowledge_project_aliases
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION public.guard_reviewed_project_alias();

ALTER TABLE public.knowledge_project_aliases ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.knowledge_project_aliases FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON public.knowledge_project_aliases USING
    (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid)
    WITH CHECK
    (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid);
CREATE POLICY tenant_login_fence ON public.knowledge_project_aliases AS RESTRICTIVE
    FOR ALL TO PUBLIC USING (public.masterbrain_tenant_login_allows(tenant_id))
    WITH CHECK (public.masterbrain_tenant_login_allows(tenant_id));
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON public.knowledge_project_aliases
    FOR EACH ROW EXECUTE FUNCTION public.deny_evidence_mutation();
CREATE TRIGGER protected_no_truncate BEFORE TRUNCATE ON public.knowledge_project_aliases
    FOR EACH STATEMENT EXECUTE FUNCTION public.deny_protected_truncate();

COMMIT;
