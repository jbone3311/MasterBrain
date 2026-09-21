BEGIN;
CREATE TABLE memory_records (
    tenant_id uuid NOT NULL,
    account_id uuid NOT NULL,
    id uuid NOT NULL,
    kind text NOT NULL CHECK (kind IN ('trip','flight','hotel','bill')),
    PRIMARY KEY (tenant_id,id),
    UNIQUE (tenant_id,account_id,id),
    FOREIGN KEY (tenant_id,account_id) REFERENCES mail_accounts(tenant_id,id)
);
CREATE TABLE memory_revisions (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    account_id uuid NOT NULL,
    record_id uuid NOT NULL,
    revision bigint NOT NULL CHECK (revision>0),
    actor_id uuid NOT NULL,
    evidence_id uuid NOT NULL,
    source_quote text NOT NULL CHECK (length(source_quote) BETWEEN 1 AND 2000),
    parent_trip_id uuid,
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload)='object' AND octet_length(payload::text)<=16000),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,revision),
    UNIQUE (tenant_id,id),
    FOREIGN KEY (tenant_id,account_id,record_id) REFERENCES memory_records(tenant_id,account_id,id),
    FOREIGN KEY (tenant_id,account_id,parent_trip_id) REFERENCES memory_records(tenant_id,account_id,id),
    FOREIGN KEY (tenant_id,account_id,evidence_id) REFERENCES message_versions(tenant_id,account_id,id)
);
CREATE INDEX memory_record_history ON memory_revisions(tenant_id,record_id,revision DESC);
CREATE INDEX memory_account_changes ON memory_revisions(tenant_id,account_id,revision);
CREATE TABLE memory_receipts (
    tenant_id uuid NOT NULL,
    actor_id uuid NOT NULL,
    idempotency_key uuid NOT NULL,
    request_hash text NOT NULL CHECK (request_hash ~ '^[a-f0-9]{64}$'),
    result_revision bigint NOT NULL,
    changed boolean NOT NULL,
    PRIMARY KEY (tenant_id,actor_id,idempotency_key),
    FOREIGN KEY (tenant_id,result_revision) REFERENCES memory_revisions(tenant_id,revision)
);
DO $block$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY['memory_records','memory_revisions','memory_receipts'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', table_name);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', table_name);
        EXECUTE format('CREATE POLICY tenant_isolation ON %I USING
            (tenant_id=nullif(current_setting(''email_brain.tenant_id'',true),'''')::uuid)
            WITH CHECK (tenant_id=nullif(current_setting(''email_brain.tenant_id'',true),'''')::uuid)', table_name);
        EXECUTE format('CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON %I
            FOR EACH ROW EXECUTE FUNCTION deny_evidence_mutation()', table_name);
    END LOOP;
END $block$;
COMMIT;
