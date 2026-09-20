BEGIN;

-- Set only by the enrollment administrator, never discovered and overwritten by a worker.
ALTER TABLE mail_accounts ADD COLUMN provider_account_id text
    CHECK (length(provider_account_id) BETWEEN 1 AND 512);

CREATE TABLE sync_workers (
    tenant_id uuid NOT NULL,
    account_id uuid NOT NULL,
    lease_token uuid,
    lease_until timestamptz NOT NULL DEFAULT '-infinity',
    next_attempt_at timestamptz NOT NULL DEFAULT '-infinity',
    failures integer NOT NULL DEFAULT 0 CHECK (failures BETWEEN 0 AND 1000),
    paused boolean NOT NULL DEFAULT false,
    last_outcome text NOT NULL DEFAULT 'new' CHECK (last_outcome IN
        ('new','progress','caught_up','retry','auth_required','protocol_error','parse_error','resync_required')),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id,account_id),
    FOREIGN KEY (tenant_id,account_id) REFERENCES mail_accounts(tenant_id,id)
);

CREATE TABLE sync_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    account_id uuid NOT NULL,
    request_id uuid NOT NULL,
    outcome text NOT NULL CHECK (outcome IN
        ('progress','caught_up','retry','auth_required','protocol_error','parse_error','resync_required')),
    event_count integer NOT NULL CHECK (event_count BETWEEN 0 AND 100),
    recorded_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (tenant_id,account_id) REFERENCES mail_accounts(tenant_id,id)
);

ALTER TABLE sync_workers ENABLE ROW LEVEL SECURITY;
ALTER TABLE sync_workers FORCE ROW LEVEL SECURITY;
ALTER TABLE sync_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE sync_runs FORCE ROW LEVEL SECURITY;
CREATE POLICY sync_workers_isolation ON sync_workers
    USING (tenant_id = nullif(current_setting('email_brain.tenant_id',true),'')::uuid)
    WITH CHECK (tenant_id = nullif(current_setting('email_brain.tenant_id',true),'')::uuid);
CREATE POLICY sync_runs_isolation ON sync_runs
    USING (tenant_id = nullif(current_setting('email_brain.tenant_id',true),'')::uuid)
    WITH CHECK (tenant_id = nullif(current_setting('email_brain.tenant_id',true),'')::uuid);

CREATE TRIGGER sync_runs_immutable BEFORE UPDATE OR DELETE ON sync_runs
    FOR EACH ROW EXECUTE FUNCTION deny_evidence_mutation();

ALTER TABLE messages ADD COLUMN provider_metadata jsonb NOT NULL DEFAULT '{}'::jsonb;

COMMIT;
