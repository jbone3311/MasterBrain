BEGIN;
ALTER TABLE messages ADD UNIQUE(tenant_id,account_id,id);
ALTER TABLE message_versions ADD UNIQUE(tenant_id,account_id,id);
ALTER TABLE message_versions DROP CONSTRAINT message_versions_tenant_id_message_id_fkey;
ALTER TABLE message_versions ADD FOREIGN KEY(tenant_id,account_id,message_id)
    REFERENCES messages(tenant_id,account_id,id);
CREATE TABLE attachment_receipts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    account_id uuid NOT NULL,
    evidence_id uuid NOT NULL,
    part_id text NOT NULL,
    original_filename text NOT NULL,
    safe_filename text NOT NULL,
    media_type text NOT NULL,
    sha256 text NOT NULL,
    byte_size integer NOT NULL CHECK (byte_size >= 0),
    status text NOT NULL CHECK (status IN ('extracted','failed','skipped','deferred','pending')),
    reason text NOT NULL,
    extracted_text text NOT NULL DEFAULT '',
    scanner_status text NOT NULL DEFAULT 'not_scanned',
    duplicate_of uuid,
    received_at timestamptz NOT NULL DEFAULT now(),
    search_document tsvector GENERATED ALWAYS AS (to_tsvector('simple',extracted_text)) STORED,
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, evidence_id, part_id),
    FOREIGN KEY (tenant_id, account_id) REFERENCES mail_accounts(tenant_id, id),
    FOREIGN KEY (tenant_id, account_id, evidence_id)
        REFERENCES message_versions(tenant_id, account_id, id),
    FOREIGN KEY (tenant_id, duplicate_of) REFERENCES attachment_receipts(tenant_id, id),
    CHECK (status='extracted' OR extracted_text='')
);
CREATE INDEX attachment_hash ON attachment_receipts(tenant_id,account_id,sha256);
CREATE INDEX attachment_fts ON attachment_receipts USING gin(search_document);
CREATE TABLE intake_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    receipt_id uuid NOT NULL,
    actor_id uuid NOT NULL,
    state text NOT NULL,
    reason text NOT NULL,
    sha256 text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (tenant_id,receipt_id) REFERENCES attachment_receipts(tenant_id,id)
);
DO $block$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY['attachment_receipts','intake_events'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', table_name);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', table_name);
        EXECUTE format('CREATE POLICY tenant_isolation ON %I USING
          (tenant_id=nullif(current_setting(''email_brain.tenant_id'',true),'''')::uuid)
          WITH CHECK
          (tenant_id=nullif(current_setting(''email_brain.tenant_id'',true),'''')::uuid)', table_name);
    END LOOP;
END $block$;
CREATE TRIGGER intake_events_append_only BEFORE UPDATE OR DELETE ON intake_events
    FOR EACH ROW EXECUTE FUNCTION deny_evidence_mutation();

-- SET LOCAL can leave an empty custom setting on pooled connections. Deny, do not cast ''.
DO $block$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'tenant_memberships','mail_accounts','sync_cursors','provider_events','audit_events'
    ] LOOP
        EXECUTE format('ALTER POLICY %I ON %I USING
          (tenant_id=nullif(current_setting(''email_brain.tenant_id'',true),'''')::uuid)
          WITH CHECK
          (tenant_id=nullif(current_setting(''email_brain.tenant_id'',true),'''')::uuid)',
          table_name || '_isolation', table_name);
    END LOOP;
END $block$;
COMMIT;
