BEGIN;

-- Cluster-global marker. It carries no data privileges and may already exist
-- when another database in the same disposable cluster applied this migration.
DO $$
DECLARE existing pg_roles%ROWTYPE;
BEGIN
    SELECT * INTO existing FROM pg_roles WHERE rolname = 'masterbrain_tenant_runtime';
    IF NOT FOUND THEN
        CREATE ROLE masterbrain_tenant_runtime NOLOGIN NOSUPERUSER NOBYPASSRLS
            NOCREATEDB NOCREATEROLE NOREPLICATION;
    ELSIF existing.rolcanlogin OR existing.rolsuper OR existing.rolbypassrls
          OR existing.rolcreatedb OR existing.rolcreaterole OR existing.rolreplication THEN
        RAISE EXCEPTION 'unsafe masterbrain_tenant_runtime role attributes';
    END IF;
END;
$$;

CREATE TABLE public.masterbrain_tenant_login_bindings (
    role_name name PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES public.tenants(id),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
ALTER TABLE public.masterbrain_tenant_login_bindings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.masterbrain_tenant_login_bindings FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.masterbrain_tenant_login_bindings FROM PUBLIC;

CREATE FUNCTION public.protect_tenant_login_binding() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
    RAISE EXCEPTION 'tenant runtime binding cannot be retargeted';
END;
$$;
CREATE TRIGGER tenant_login_binding_no_update
BEFORE UPDATE ON public.masterbrain_tenant_login_bindings
FOR EACH ROW EXECUTE FUNCTION public.protect_tenant_login_binding();
REVOKE ALL ON FUNCTION public.protect_tenant_login_binding() FROM PUBLIC;

CREATE FUNCTION public.audit_tenant_login_binding() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
DECLARE entry public.masterbrain_tenant_login_bindings%ROWTYPE;
BEGIN
    IF TG_OP = 'DELETE' THEN entry := OLD; ELSE entry := NEW; END IF;
    INSERT INTO public.audit_events(tenant_id,actor_id,request_id,event_type,
                                    resource_type,resource_id,outcome,metadata)
    VALUES (entry.tenant_id,NULL,pg_catalog.gen_random_uuid(),
            'tenant_login.' || pg_catalog.lower(TG_OP),
            'database_role',entry.role_name::text,'ok',
            pg_catalog.jsonb_build_object('database_role',session_user));
    RETURN NULL;
END;
$$;
CREATE TRIGGER tenant_login_binding_audit
AFTER INSERT OR DELETE ON public.masterbrain_tenant_login_bindings
FOR EACH ROW EXECUTE FUNCTION public.audit_tenant_login_binding();
REVOKE ALL ON FUNCTION public.audit_tenant_login_binding() FROM PUBLIC;

-- session_user is the authenticated login even after SET ROLE. The mapping table
-- is read only as this migration's privileged owner, not through runtime grants.
CREATE FUNCTION public.masterbrain_tenant_login_allows(candidate_tenant uuid)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp AS $$
    SELECT CASE WHEN
        pg_catalog.pg_has_role(session_user, 'masterbrain_tenant_runtime', 'member')
        OR EXISTS (
            SELECT 1 FROM public.masterbrain_tenant_login_bindings AS b
            WHERE b.role_name = session_user
        )
    THEN EXISTS (
        SELECT 1 FROM public.masterbrain_tenant_login_bindings AS b
        WHERE b.role_name = session_user AND b.tenant_id = candidate_tenant
    )
    ELSE true END
$$;
-- RLS policy expressions execute under each invoker. The boolean result carries
-- no mapping data for another login; PUBLIC may execute only this fixed predicate.
GRANT EXECUTE ON FUNCTION public.masterbrain_tenant_login_allows(uuid) TO PUBLIC;

-- SECURITY DEFINER functions bypass their target tables' RLS. Preserve their
-- existing argument/privilege contracts while applying the same login fence.
CREATE OR REPLACE FUNCTION public.resolve_external_identity(
    requested_issuer text, requested_subject text, requested_client_id text
) RETURNS TABLE (
    id uuid, tenant_id uuid, actor_id uuid, scopes text[],
    client_kind text, revision bigint
) LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
    SELECT e.id, e.tenant_id, e.actor_id, e.scopes, e.client_kind, e.revision
    FROM public.external_identities AS e
    WHERE e.active
      AND e.issuer = requested_issuer
      AND e.subject = requested_subject
      AND e.client_id = requested_client_id
      AND public.masterbrain_tenant_login_allows(e.tenant_id)
$$;

CREATE OR REPLACE FUNCTION public.lock_recovery_owners(
    account uuid, requester uuid, worker uuid
) RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog AS $$
DECLARE
    context_tenant uuid := nullif(current_setting('email_brain.tenant_id',true),'')::uuid;
    matched integer;
BEGIN
    IF context_tenant IS NULL OR account IS NULL OR requester IS NULL OR worker IS NULL
       OR NOT public.masterbrain_tenant_login_allows(context_tenant) THEN
        RETURN false;
    END IF;
    PERFORM a.id FROM public.mail_accounts a
        WHERE a.tenant_id=context_tenant AND a.id=account AND a.status='active' FOR SHARE;
    IF NOT FOUND THEN RETURN false; END IF;
    SELECT count(*) INTO matched FROM (
        SELECT m.user_id FROM public.tenant_memberships m
        WHERE m.tenant_id=context_tenant AND m.user_id IN (requester,worker)
          AND m.role='owner'
        ORDER BY m.user_id FOR SHARE
    ) locked;
    RETURN matched = CASE WHEN requester=worker THEN 1 ELSE 2 END;
END;
$$;

DO $$
DECLARE r record;
DECLARE tenant_column text;
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_class AS c
        JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
        JOIN pg_catalog.pg_attribute AS a ON a.attrelid = c.oid
        WHERE n.nspname = 'public' AND c.relkind = 'r'
          AND a.attname = 'tenant_id' AND a.attnum > 0
          AND (NOT c.relrowsecurity OR NOT c.relforcerowsecurity)
    ) THEN
        RAISE EXCEPTION 'tenant column table lacks forced RLS';
    END IF;
    FOR r IN
        SELECT c.relname, c.oid
        FROM pg_catalog.pg_class AS c
        JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'r' AND c.relrowsecurity
        ORDER BY c.relname
    LOOP
        IF NOT (SELECT relforcerowsecurity FROM pg_catalog.pg_class WHERE oid = r.oid) THEN
            RAISE EXCEPTION 'tenant fence requires FORCE RLS on %', r.relname;
        END IF;
        tenant_column := CASE WHEN r.relname = 'tenants' THEN 'id' ELSE 'tenant_id' END;
        IF NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_attribute
            WHERE attrelid = r.oid AND attname = tenant_column AND attnum > 0
        ) THEN
            RAISE EXCEPTION 'tenant fence missing tenant column on %', r.relname;
        END IF;
        EXECUTE format(
            'CREATE POLICY tenant_login_fence ON public.%I AS RESTRICTIVE '
            || 'FOR ALL TO PUBLIC USING (public.masterbrain_tenant_login_allows(%I)) '
            || 'WITH CHECK (public.masterbrain_tenant_login_allows(%I))',
            r.relname, tenant_column, tenant_column
        );
    END LOOP;
END;
$$;

COMMIT;
