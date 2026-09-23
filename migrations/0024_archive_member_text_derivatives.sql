BEGIN;

CREATE TABLE brain_archive_member_text_receipts (
    tenant_id uuid NOT NULL,
    actor_id uuid NOT NULL,
    idempotency_key uuid NOT NULL,
    inventory_id text NOT NULL,
    member_locator text NOT NULL CHECK (length(member_locator) BETWEEN 1 AND 1024),
    parent_source_version_id text NOT NULL,
    parent_evidence_id text NOT NULL,
    source_id text NOT NULL,
    item_id text NOT NULL,
    version_id text NOT NULL,
    evidence_id text NOT NULL,
    document_id text NOT NULL,
    normalizer text NOT NULL CHECK (length(normalizer) BETWEEN 1 AND 200),
    chunk_count integer NOT NULL CHECK (chunk_count > 0),
    code_revision text NOT NULL CHECK (length(code_revision) BETWEEN 1 AND 200),
    request_hash text NOT NULL CHECK (request_hash ~ '^[a-f0-9]{64}$'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,actor_id,idempotency_key),
    FOREIGN KEY (tenant_id,inventory_id,member_locator)
        REFERENCES brain_archive_members(tenant_id,inventory_id,locator),
    FOREIGN KEY (tenant_id,parent_evidence_id) REFERENCES brain_evidence(tenant_id,id),
    FOREIGN KEY (tenant_id,source_id,item_id,version_id)
        REFERENCES brain_source_versions(tenant_id,source_id,item_id,id),
    FOREIGN KEY (tenant_id,evidence_id) REFERENCES brain_evidence(tenant_id,id),
    FOREIGN KEY (tenant_id,document_id) REFERENCES brain_normalized_documents(tenant_id,id)
);

ALTER TABLE brain_archive_member_text_receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE brain_archive_member_text_receipts FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON brain_archive_member_text_receipts USING
    (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid)
    WITH CHECK
    (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid);
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON brain_archive_member_text_receipts
    FOR EACH ROW EXECUTE FUNCTION deny_evidence_mutation();

COMMIT;
