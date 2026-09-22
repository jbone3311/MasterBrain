BEGIN;

ALTER TABLE document_jobs ADD UNIQUE (tenant_id,id);
ALTER TABLE document_extractions ADD UNIQUE (tenant_id,id);

CREATE TABLE brain_email_document_bridge_receipts (
    tenant_id uuid NOT NULL,
    actor_id uuid NOT NULL,
    idempotency_key uuid NOT NULL,
    account_id uuid NOT NULL,
    legacy_attachment_id uuid NOT NULL,
    legacy_extraction_id uuid NOT NULL,
    legacy_approval_job_id uuid NOT NULL,
    source_id text NOT NULL CHECK (source_id ~ '^[a-z][a-z0-9_-]{0,127}$'),
    item_id text NOT NULL CHECK (item_id ~ '^[a-z][a-z0-9_-]{0,127}$'),
    version_id text NOT NULL CHECK (version_id ~ '^[a-z][a-z0-9_-]{0,127}$'),
    evidence_id text NOT NULL CHECK (evidence_id ~ '^[a-z][a-z0-9_-]{0,127}$'),
    document_id text NOT NULL CHECK (document_id ~ '^[a-z][a-z0-9_-]{0,127}$'),
    chunk_count integer NOT NULL CHECK (chunk_count > 0),
    extraction_status text NOT NULL CHECK (extraction_status IN ('extracted','partial')),
    extraction_revision integer NOT NULL CHECK (extraction_revision > 0),
    processor_version text NOT NULL CHECK (length(processor_version) BETWEEN 1 AND 200),
    policy_version text NOT NULL CHECK (length(policy_version) BETWEEN 1 AND 200),
    normalizer text NOT NULL CHECK (length(normalizer) BETWEEN 1 AND 200),
    result_sha256 text NOT NULL CHECK (result_sha256 ~ '^[a-f0-9]{64}$'),
    code_revision text NOT NULL CHECK (length(code_revision) BETWEEN 1 AND 200),
    request_hash text NOT NULL CHECK (request_hash ~ '^[a-f0-9]{64}$'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,actor_id,idempotency_key),
    UNIQUE (tenant_id,legacy_extraction_id),
    FOREIGN KEY (tenant_id,account_id,legacy_attachment_id)
        REFERENCES attachment_receipts(tenant_id,account_id,id),
    FOREIGN KEY (tenant_id,legacy_extraction_id)
        REFERENCES document_extractions(tenant_id,id),
    FOREIGN KEY (tenant_id,legacy_approval_job_id)
        REFERENCES document_jobs(tenant_id,id),
    FOREIGN KEY (tenant_id,source_id,item_id,version_id)
        REFERENCES brain_source_versions(tenant_id,source_id,item_id,id),
    FOREIGN KEY (tenant_id,evidence_id) REFERENCES brain_evidence(tenant_id,id),
    FOREIGN KEY (tenant_id,document_id) REFERENCES brain_normalized_documents(tenant_id,id)
);

ALTER TABLE brain_email_document_bridge_receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE brain_email_document_bridge_receipts FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON brain_email_document_bridge_receipts USING
    (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid)
    WITH CHECK
    (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid);
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON brain_email_document_bridge_receipts
    FOR EACH ROW EXECUTE FUNCTION deny_evidence_mutation();

COMMIT;
