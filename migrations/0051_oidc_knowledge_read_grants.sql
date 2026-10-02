BEGIN;

-- ADR-143: admit direct Knowledge read scopes only through the same enrolled
-- assistant/source-grant fences as the existing Brain reads. Preserve old
-- resolver refusal because old binaries cannot represent source grants.
ALTER TABLE public.external_identities
    DROP CONSTRAINT external_identities_scopes_check;
ALTER TABLE public.external_identities ADD CONSTRAINT external_identities_scopes_check
    CHECK (
        cardinality(scopes) BETWEEN 1 AND 12
        AND array_ndims(scopes) = 1
        AND array_position(scopes, NULL) IS NULL
        AND scopes <@ ARRAY[
            'email.search','email.evidence.read','email.proposal.create',
            'email.proposal.read','email.review','brain.search',
            'knowledge.search','knowledge.read','knowledge.changes.read',
            'brain.evidence.read','brain.content.read','brain.changes.read'
        ]::text[]
    );
ALTER TABLE public.external_identities
    DROP CONSTRAINT external_identity_assistant_brain_fence;
ALTER TABLE public.external_identities ADD CONSTRAINT external_identity_assistant_brain_fence
    CHECK (
        client_kind <> 'assistant' OR NOT (
            scopes && ARRAY['brain.search','knowledge.search','knowledge.read',
                             'knowledge.changes.read','brain.evidence.read',
                             'brain.content.read','brain.changes.read']::text[]
            AND scopes && ARRAY['email.search','email.evidence.read',
                                 'email.proposal.create','email.proposal.read',
                                 'email.review']::text[]
        )
    );

CREATE OR REPLACE FUNCTION public.validate_external_identity_source_eligibility()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM public.external_identity_sources AS g
        WHERE g.tenant_id=NEW.tenant_id AND g.binding_id=NEW.id
    ) AND (
        NEW.client_kind <> 'assistant' OR NOT (
            NEW.scopes && ARRAY['brain.search','knowledge.search','knowledge.read',
                                 'knowledge.changes.read','brain.evidence.read',
                                 'brain.content.read','brain.changes.read']::text[]
        )
    ) THEN
        RAISE EXCEPTION 'source grants require an assistant Brain binding';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.audit_external_identity_source_change()
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
        binding.scopes && ARRAY['brain.search','knowledge.search','knowledge.read',
                                 'knowledge.changes.read','brain.evidence.read',
                                 'brain.content.read','brain.changes.read']::text[]
    ) THEN
        RAISE EXCEPTION 'source grant has no active assistant Brain binding';
    END IF;
    SELECT count(*) INTO grant_count FROM public.external_identity_sources AS g
        WHERE g.tenant_id=entry.tenant_id AND g.binding_id=entry.binding_id;
    IF grant_count > 20 THEN
        RAISE EXCEPTION 'source grant limit exceeded';
    END IF;
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

CREATE OR REPLACE FUNCTION public.resolve_external_identity(
    requested_issuer text, requested_subject text, requested_client_id text
) RETURNS TABLE (
    id uuid, tenant_id uuid, actor_id uuid, scopes text[],
    client_kind text, revision bigint
) LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
    SELECT e.id,e.tenant_id,e.actor_id,e.scopes,e.client_kind,e.revision
    FROM public.external_identities AS e
    WHERE e.active
      AND e.issuer=requested_issuer
      AND e.subject=requested_subject
      AND e.client_id=requested_client_id
      AND NOT (
          e.client_kind='assistant' AND
          e.scopes && ARRAY['brain.search','knowledge.search','knowledge.read',
                            'knowledge.changes.read','brain.evidence.read',
                            'brain.content.read','brain.changes.read']::text[]
      )
      AND public.masterbrain_tenant_login_allows(e.tenant_id)
$$;

COMMIT;
