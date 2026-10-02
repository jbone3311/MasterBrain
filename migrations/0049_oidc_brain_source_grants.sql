BEGIN;

-- Brain operations are admitted by an administrator binding, never JWT claims.
ALTER TABLE public.external_identities
    DROP CONSTRAINT external_identities_scopes_check;
ALTER TABLE public.external_identities ADD CONSTRAINT external_identities_scopes_check
    CHECK (
        cardinality(scopes) BETWEEN 1 AND 9
        AND array_ndims(scopes) = 1
        AND array_position(scopes, NULL) IS NULL
        AND scopes <@ ARRAY[
            'email.search','email.evidence.read','email.proposal.create',
            'email.proposal.read','email.review','brain.search',
            'knowledge.search','brain.evidence.read','brain.content.read'
        ]::text[]
    );
ALTER TABLE public.external_identities ADD CONSTRAINT external_identity_assistant_brain_fence
    CHECK (
        client_kind <> 'assistant' OR NOT (
            scopes && ARRAY['brain.search','knowledge.search',
                             'brain.evidence.read','brain.content.read']::text[]
            AND scopes && ARRAY['email.search','email.evidence.read',
                                 'email.proposal.create','email.proposal.read',
                                 'email.review']::text[]
        )
    );

-- The composite keys prevent a grant from crossing either the identity's or
-- source's tenant. A removed source cannot silently revive a stale enrollment.
ALTER TABLE public.external_identities ADD CONSTRAINT external_identities_tenant_id_id_key
    UNIQUE (tenant_id,id);
CREATE TABLE public.external_identity_sources (
    tenant_id uuid NOT NULL,
    binding_id uuid NOT NULL,
    source_id text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,binding_id,source_id),
    FOREIGN KEY (tenant_id,binding_id)
        REFERENCES public.external_identities(tenant_id,id),
    FOREIGN KEY (tenant_id,source_id)
        REFERENCES public.brain_sources(tenant_id,id)
);
CREATE INDEX external_identity_sources_by_binding
    ON public.external_identity_sources(binding_id,source_id);
ALTER TABLE public.external_identity_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.external_identity_sources FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.external_identity_sources FROM PUBLIC;
GRANT SELECT,INSERT,DELETE ON public.external_identity_sources
    TO masterbrain_identity_admin;
CREATE POLICY identity_admin_source_management ON public.external_identity_sources
    FOR ALL TO masterbrain_identity_admin USING (true) WITH CHECK (true);
CREATE POLICY tenant_login_fence
    ON public.external_identity_sources AS RESTRICTIVE FOR ALL
    USING (public.masterbrain_tenant_login_allows(tenant_id))
    WITH CHECK (public.masterbrain_tenant_login_allows(tenant_id));

CREATE FUNCTION public.validate_external_identity_source_eligibility()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM public.external_identity_sources AS g
        WHERE g.tenant_id=NEW.tenant_id AND g.binding_id=NEW.id
    ) AND (
        NEW.client_kind <> 'assistant' OR NOT (
            NEW.scopes && ARRAY['brain.search','knowledge.search',
                                 'brain.evidence.read','brain.content.read']::text[]
        )
    ) THEN
        RAISE EXCEPTION 'source grants require an assistant Brain binding';
    END IF;
    RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION public.validate_external_identity_source_eligibility()
    FROM PUBLIC;
CREATE TRIGGER external_identity_source_eligibility
    BEFORE INSERT OR UPDATE ON public.external_identities FOR EACH ROW
    EXECUTE FUNCTION public.validate_external_identity_source_eligibility();

CREATE FUNCTION public.audit_external_identity_source_change()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp AS $$
DECLARE
    entry public.external_identity_sources%ROWTYPE;
    binding public.external_identities%ROWTYPE;
    grant_count integer;
BEGIN
    IF TG_OP='DELETE' THEN entry := OLD; ELSE entry := NEW; END IF;
    SELECT * INTO binding FROM public.external_identities AS e
        WHERE e.tenant_id=entry.tenant_id AND e.id=entry.binding_id FOR UPDATE;
    IF NOT FOUND OR binding.client_kind <> 'assistant' OR NOT (
        binding.scopes && ARRAY['brain.search','knowledge.search',
                                 'brain.evidence.read','brain.content.read']::text[]
    ) THEN
        RAISE EXCEPTION 'source grant has no active assistant Brain binding';
    END IF;
    SELECT count(*) INTO grant_count FROM public.external_identity_sources AS g
        WHERE g.tenant_id=entry.tenant_id AND g.binding_id=entry.binding_id;
    IF grant_count > 20 THEN
        RAISE EXCEPTION 'source grant limit exceeded';
    END IF;
    -- Existing binding protection bumps revision and audits the binding change.
    UPDATE public.external_identities SET active=active
        WHERE tenant_id=entry.tenant_id AND id=entry.binding_id;
    INSERT INTO public.audit_events(
        tenant_id,actor_id,request_id,event_type,resource_type,resource_id,outcome,metadata
    ) VALUES (
        entry.tenant_id,NULL,pg_catalog.gen_random_uuid(),
        'source_grant.' || pg_catalog.lower(TG_OP),
        'external_identity_source',entry.binding_id::text,'ok',
        pg_catalog.jsonb_build_object('database_role',session_user,
                                      'source_id',entry.source_id)
    );
    RETURN NULL;
END;
$$;
REVOKE ALL ON FUNCTION public.audit_external_identity_source_change() FROM PUBLIC;
CREATE TRIGGER external_identity_source_change
    AFTER INSERT OR DELETE ON public.external_identity_sources FOR EACH ROW
    EXECUTE FUNCTION public.audit_external_identity_source_change();

-- New binaries use only this exact-key resolver. Keep the old Email-only
-- resolver for rolling compatibility; it cannot return any source enrollment.
CREATE FUNCTION public.resolve_external_identity_v2(
    requested_issuer text, requested_subject text, requested_client_id text
) RETURNS TABLE (
    id uuid, tenant_id uuid, actor_id uuid, scopes text[],
    client_kind text, revision bigint, source_ids text[]
) LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
    SELECT e.id,e.tenant_id,e.actor_id,e.scopes,e.client_kind,e.revision,
        ARRAY(
            SELECT g.source_id FROM public.external_identity_sources AS g
            WHERE g.tenant_id=e.tenant_id AND g.binding_id=e.id
            ORDER BY g.source_id
        ) AS source_ids
    FROM public.external_identities AS e
    WHERE e.active
      AND e.issuer=requested_issuer
      AND e.subject=requested_subject
      AND e.client_id=requested_client_id
      AND public.masterbrain_tenant_login_allows(e.tenant_id)
$$;
REVOKE ALL ON FUNCTION public.resolve_external_identity_v2(text,text,text) FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='email_brain_runtime') THEN
        GRANT EXECUTE ON FUNCTION public.resolve_external_identity_v2(text,text,text)
            TO email_brain_runtime;
    END IF;
END;
$$;

COMMIT;
