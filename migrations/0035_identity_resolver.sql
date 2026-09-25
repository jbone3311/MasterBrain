BEGIN;

-- Resolve only one exact verified tuple. The caller receives no table-wide SELECT
-- privilege; this function's fixed body and search path are the trust boundary.
CREATE FUNCTION resolve_external_identity(
    requested_issuer text, requested_subject text, requested_client_id text
) RETURNS TABLE (
    id uuid, tenant_id uuid, actor_id uuid, scopes text[],
    client_kind text, revision bigint
) LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    SELECT e.id, e.tenant_id, e.actor_id, e.scopes, e.client_kind, e.revision
    FROM public.external_identities AS e
    WHERE e.active
      AND e.issuer = requested_issuer
      AND e.subject = requested_subject
      AND e.client_id = requested_client_id
$$;
REVOKE ALL ON FUNCTION resolve_external_identity(text,text,text) FROM PUBLIC;

-- The old policy trusted caller-settable GUCs. Keep the administrator's separate
-- role-targeted policy from 0034; runtime lookup now goes through the function.
DROP POLICY verified_identity_lookup ON external_identities;

-- The standard runtime role may not exist yet on a greenfield database. Existing
-- custom runtime grants are removed by the required grant-runtime refresh.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'email_brain_runtime') THEN
        REVOKE SELECT ON external_identities FROM email_brain_runtime;
        GRANT EXECUTE ON FUNCTION resolve_external_identity(text,text,text)
            TO email_brain_runtime;
    END IF;
END;
$$;

COMMIT;
