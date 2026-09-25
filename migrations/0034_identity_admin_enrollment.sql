BEGIN;

-- Cluster-global role; migration may also run in multiple disposable databases.
DO $$
DECLARE existing pg_roles%ROWTYPE;
BEGIN
    SELECT * INTO existing FROM pg_roles WHERE rolname = 'masterbrain_identity_admin';
    IF NOT FOUND THEN
        CREATE ROLE masterbrain_identity_admin NOLOGIN NOSUPERUSER NOBYPASSRLS
            NOCREATEDB NOCREATEROLE NOREPLICATION;
    ELSIF existing.rolcanlogin OR existing.rolsuper OR existing.rolbypassrls
          OR existing.rolcreatedb OR existing.rolcreaterole OR existing.rolreplication THEN
        RAISE EXCEPTION 'unsafe masterbrain_identity_admin role attributes';
    ELSIF EXISTS (SELECT 1 FROM pg_auth_members WHERE roleid = existing.oid) THEN
        RAISE EXCEPTION 'existing masterbrain_identity_admin role has members; review before grant';
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA public TO masterbrain_identity_admin;
GRANT SELECT, INSERT, UPDATE, DELETE ON external_identities
    TO masterbrain_identity_admin;

CREATE POLICY identity_admin_management ON external_identities
    FOR ALL TO masterbrain_identity_admin
    USING (true) WITH CHECK (true);

-- The invoker needs no direct INSERT privilege or RLS bypass on audit_events.
-- session_user retains the connecting administrator login under SECURITY DEFINER.
CREATE OR REPLACE FUNCTION audit_external_identity() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE entry public.external_identities%ROWTYPE;
BEGIN
    IF TG_OP = 'DELETE' THEN entry := OLD; ELSE entry := NEW; END IF;
    INSERT INTO public.audit_events(tenant_id,actor_id,request_id,event_type,resource_type,
                                    resource_id,outcome,metadata)
    VALUES (entry.tenant_id,NULL,gen_random_uuid(),'identity.' || lower(TG_OP),
            'external_identity',entry.id::text,'ok',
            jsonb_build_object('database_role',session_user,'revision',entry.revision,
                               'active',entry.active,'scopes',entry.scopes,
                               'client_kind',entry.client_kind));
    RETURN NULL;
END;
$$;
REVOKE ALL ON FUNCTION audit_external_identity() FROM PUBLIC;

COMMIT;
