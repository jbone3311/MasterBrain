BEGIN;

ALTER TABLE recovery_attempts ADD UNIQUE
    (tenant_id,account_id,receipt_id,parser_version,id,outcome);

CREATE TABLE recovery_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    account_id uuid NOT NULL,
    receipt_id uuid NOT NULL,
    actor_id uuid NOT NULL,
    approval_scopes text[] NOT NULL DEFAULT ARRAY['email.evidence.read','email.review'],
    idempotency_key uuid NOT NULL,
    parser_version text NOT NULL CHECK (parser_version ~ '^sandbox-mime-v1-[a-f0-9]{64}$'),
    created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
    expires_at timestamptz NOT NULL DEFAULT statement_timestamp() + interval '1 hour',
    status text NOT NULL DEFAULT 'queued' CHECK (status IN
        ('queued','running','retry_wait','completed','cancelled','expired','failed','stale','revoked')),
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 3),
    lease_token uuid,
    lease_until timestamptz,
    worker_actor_id uuid,
    retry_at timestamptz,
    completed_at timestamptz,
    attempt_id uuid,
    outcome text CHECK (outcome IN
        ('recovered','mime_rejected','integrity_failed','cancelled','approval_expired',
         'attempts_exhausted','infrastructure_unavailable','authorization_revoked','source_changed')),
    UNIQUE (tenant_id,actor_id,idempotency_key),
    FOREIGN KEY (tenant_id,account_id,receipt_id)
        REFERENCES quarantine_receipts(tenant_id,account_id,id),
    FOREIGN KEY (tenant_id,account_id,receipt_id,parser_version,attempt_id,outcome)
        REFERENCES recovery_attempts(tenant_id,account_id,receipt_id,parser_version,id,outcome),
    CHECK (approval_scopes = ARRAY['email.evidence.read','email.review']::text[]),
    CHECK (expires_at = created_at + interval '1 hour'),
    CHECK ((status='running') = (lease_token IS NOT NULL AND lease_until IS NOT NULL)),
    CHECK (status='running' OR (lease_token IS NULL AND lease_until IS NULL)),
    CHECK (status<>'running' OR (worker_actor_id IS NOT NULL AND attempts>0 AND retry_at IS NULL)),
    CHECK (status<>'queued' OR (attempts=0 AND worker_actor_id IS NULL AND retry_at IS NULL)),
    CHECK ((status='retry_wait') = (retry_at IS NOT NULL)),
    CHECK (status<>'retry_wait' OR attempts BETWEEN 1 AND 2),
    CHECK ((status='completed') = (attempt_id IS NOT NULL)),
    CHECK ((status IN ('completed','cancelled','expired','failed','stale','revoked'))
           = (completed_at IS NOT NULL)),
    CHECK (CASE status
        WHEN 'queued' THEN outcome IS NULL
        WHEN 'running' THEN outcome IS NULL
        WHEN 'retry_wait' THEN outcome='infrastructure_unavailable'
        WHEN 'completed' THEN outcome IN ('recovered','mime_rejected','integrity_failed')
        WHEN 'cancelled' THEN outcome='cancelled'
        WHEN 'expired' THEN outcome='approval_expired'
        WHEN 'failed' THEN outcome IN ('attempts_exhausted','infrastructure_unavailable')
        WHEN 'stale' THEN outcome='source_changed'
        WHEN 'revoked' THEN outcome='authorization_revoked'
        ELSE false END),
    CHECK (status IN ('queued','running') OR outcome IS NOT NULL)
);
CREATE INDEX recovery_jobs_account_queue ON recovery_jobs(tenant_id,account_id,created_at,id)
    WHERE status IN ('queued','running','retry_wait');
ALTER TABLE recovery_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE recovery_jobs FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON recovery_jobs
    USING (tenant_id = nullif(current_setting('email_brain.tenant_id',true),'')::uuid)
    WITH CHECK (tenant_id = nullif(current_setting('email_brain.tenant_id',true),'')::uuid);

CREATE FUNCTION protect_recovery_job() RETURNS trigger LANGUAGE plpgsql AS $function$
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'recovery approval is retained';
    END IF;
    IF (NEW.id,NEW.tenant_id,NEW.account_id,NEW.receipt_id,NEW.actor_id,NEW.approval_scopes,
        NEW.idempotency_key,NEW.parser_version,NEW.created_at,NEW.expires_at)
       IS DISTINCT FROM
       (OLD.id,OLD.tenant_id,OLD.account_id,OLD.receipt_id,OLD.actor_id,OLD.approval_scopes,
        OLD.idempotency_key,OLD.parser_version,OLD.created_at,OLD.expires_at) THEN
        RAISE EXCEPTION 'recovery approval is immutable';
    END IF;
    IF OLD.status IN ('completed','cancelled','expired','failed','stale','revoked') THEN
        IF NEW IS DISTINCT FROM OLD THEN
            RAISE EXCEPTION 'recovery terminal state is immutable';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.status='running' THEN
        IF NEW.attempts<>OLD.attempts+1 OR NEW.lease_token IS NULL
           OR NEW.lease_token IS NOT DISTINCT FROM OLD.lease_token
           OR (OLD.status='running' AND OLD.lease_until>clock_timestamp())
           OR (OLD.status='retry_wait' AND OLD.retry_at>clock_timestamp()) THEN
            RAISE EXCEPTION 'invalid recovery claim transition';
        END IF;
    ELSIF NEW.attempts<>OLD.attempts THEN
        RAISE EXCEPTION 'recovery claims cannot be rewritten';
    END IF;
    IF NEW.status IN ('queued') OR
       (NEW.status IN ('completed','retry_wait') AND OLD.status<>'running') THEN
        RAISE EXCEPTION 'invalid recovery state transition';
    END IF;
    RETURN NEW;
END $function$;
CREATE TRIGGER recovery_jobs_protected BEFORE UPDATE OR DELETE ON recovery_jobs
    FOR EACH ROW EXECUTE FUNCTION protect_recovery_job();

-- FOR SHARE normally requires UPDATE privileges. This narrowly scoped read/lock
-- helper avoids granting runtime permission to edit accounts or memberships.
CREATE FUNCTION lock_recovery_owners(account uuid, requester uuid, worker uuid)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $function$
DECLARE
    context_tenant uuid := nullif(current_setting('email_brain.tenant_id',true),'')::uuid;
    matched integer;
BEGIN
    IF context_tenant IS NULL OR account IS NULL OR requester IS NULL OR worker IS NULL THEN
        RETURN false;
    END IF;
    PERFORM a.id FROM public.mail_accounts a
        WHERE a.tenant_id=context_tenant AND a.id=account AND a.status='active' FOR SHARE;
    IF NOT FOUND THEN RETURN false; END IF;
    SELECT count(*) INTO matched FROM (
        SELECT m.user_id FROM public.tenant_memberships m
        WHERE m.tenant_id=context_tenant AND m.user_id IN (requester,worker) AND m.role='owner'
        ORDER BY m.user_id FOR SHARE
    ) locked;
    RETURN matched = CASE WHEN requester=worker THEN 1 ELSE 2 END;
END $function$;
REVOKE ALL ON FUNCTION lock_recovery_owners(uuid,uuid,uuid) FROM PUBLIC;

COMMIT;
