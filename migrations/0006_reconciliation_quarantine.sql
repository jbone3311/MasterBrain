BEGIN;

ALTER TABLE messages ADD COLUMN quarantined boolean NOT NULL DEFAULT false;

CREATE TABLE sync_inventory (
    tenant_id uuid NOT NULL,
    account_id uuid NOT NULL,
    generation uuid NOT NULL,
    provider_id text NOT NULL CHECK (length(provider_id) BETWEEN 1 AND 1000),
    recorded_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id,account_id,generation,provider_id),
    FOREIGN KEY (tenant_id,account_id) REFERENCES mail_accounts(tenant_id,id)
);

CREATE TABLE message_sync_state (
    tenant_id uuid NOT NULL,
    account_id uuid NOT NULL,
    provider_id text NOT NULL,
    event_key text,
    status text NOT NULL CHECK (status IN ('ready','quarantined','deleted')),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id,account_id,provider_id),
    FOREIGN KEY (tenant_id,account_id) REFERENCES mail_accounts(tenant_id,id),
    FOREIGN KEY (tenant_id,account_id,event_key)
        REFERENCES provider_events(tenant_id,account_id,event_key)
);
CREATE TABLE sync_inventory_seals (
    tenant_id uuid NOT NULL,
    account_id uuid NOT NULL,
    generation uuid NOT NULL,
    total bigint NOT NULL CHECK (total BETWEEN 0 AND 2147483647),
    recorded_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id,account_id,generation),
    FOREIGN KEY (tenant_id,account_id) REFERENCES mail_accounts(tenant_id,id)
);
INSERT INTO message_sync_state(tenant_id,account_id,provider_id,status)
    SELECT tenant_id,account_id,provider_message_id,
           CASE WHEN deleted THEN 'deleted' ELSE 'ready' END FROM messages;

CREATE TABLE quarantine_receipts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    account_id uuid NOT NULL,
    event_key text NOT NULL,
    provider_id text NOT NULL,
    raw_sha256 text NOT NULL,
    reason text NOT NULL CHECK (reason = 'mime_rejected'),
    parser_version text NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id,account_id,event_key),
    FOREIGN KEY (tenant_id,account_id,event_key)
        REFERENCES provider_events(tenant_id,account_id,event_key),
    FOREIGN KEY (tenant_id,account_id,raw_sha256)
        REFERENCES raw_objects(tenant_id,account_id,sha256)
);

DO $block$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'sync_inventory','sync_inventory_seals','message_sync_state','quarantine_receipts'
    ]
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', table_name);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', table_name);
        EXECUTE format('CREATE POLICY tenant_isolation ON %I USING
            (tenant_id = nullif(current_setting(''email_brain.tenant_id'',true),'''')::uuid)
            WITH CHECK (tenant_id = nullif(current_setting(''email_brain.tenant_id'',true),'''')::uuid)',
            table_name);
    END LOOP;
END $block$;
CREATE TRIGGER inventory_immutable BEFORE UPDATE OR DELETE ON sync_inventory
    FOR EACH ROW EXECUTE FUNCTION deny_evidence_mutation();
CREATE TRIGGER quarantine_immutable BEFORE UPDATE OR DELETE ON quarantine_receipts
    FOR EACH ROW EXECUTE FUNCTION deny_evidence_mutation();
CREATE TRIGGER inventory_seals_immutable BEFORE UPDATE OR DELETE ON sync_inventory_seals
    FOR EACH ROW EXECUTE FUNCTION deny_evidence_mutation();

COMMIT;
