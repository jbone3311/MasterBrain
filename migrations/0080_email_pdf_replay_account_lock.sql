BEGIN;

-- ADR-231: lock one exact account without granting account UPDATE to workers.
-- The authenticated login, not caller-controlled GUCs, must be tenant-bound.
CREATE FUNCTION public.lock_email_pdf_replay_account(
    requested_tenant uuid, requested_account uuid
) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $function$
DECLARE active_account boolean;
BEGIN
    IF requested_tenant IS NULL OR requested_account IS NULL
       OR requested_tenant IS DISTINCT FROM
          nullif(current_setting('email_brain.tenant_id',true),'')::uuid
       OR NOT EXISTS (
           SELECT 1 FROM public.masterbrain_tenant_login_bindings b
           WHERE b.role_name=session_user AND b.tenant_id=requested_tenant
       )
       OR NOT EXISTS (
           SELECT 1 FROM public.tenant_memberships m
           WHERE m.tenant_id=requested_tenant
             AND m.user_id=nullif(current_setting('email_brain.actor_id',true),'')::uuid
       )
    THEN
        RETURN false;
    END IF;
    SELECT a.status='active' INTO active_account
    FROM public.mail_accounts a
    WHERE a.tenant_id=requested_tenant AND a.id=requested_account
    FOR SHARE;
    RETURN coalesce(active_account,false);
END
$function$;
REVOKE ALL ON FUNCTION public.lock_email_pdf_replay_account(uuid,uuid) FROM PUBLIC;

-- Existing tenant-bound logins need this exact function grant; future logins
-- receive it in grant_runtime. Do not grant through the non-inherited marker.
DO $block$
DECLARE bound_role record;
BEGIN
    FOR bound_role IN SELECT role_name FROM public.masterbrain_tenant_login_bindings LOOP
        EXECUTE format(
            'GRANT EXECUTE ON FUNCTION public.lock_email_pdf_replay_account(uuid,uuid) TO %I',
            bound_role.role_name
        );
    END LOOP;
END
$block$;

COMMIT;
