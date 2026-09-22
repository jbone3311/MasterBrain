BEGIN;

CREATE TABLE brain_parts (
    tenant_id uuid NOT NULL,
    id text NOT NULL CHECK (id ~ '^[a-z][a-z0-9_-]{0,127}$'),
    parent_evidence_id text NOT NULL,
    evidence_id text NOT NULL,
    part_path text NOT NULL CHECK (length(part_path) BETWEEN 1 AND 200),
    media_type text NOT NULL CHECK (length(media_type) BETWEEN 1 AND 200),
    sha256 text NOT NULL CHECK (sha256 ~ '^[a-f0-9]{64}$'),
    size_bytes bigint NOT NULL CHECK (size_bytes >= 0),
    status text NOT NULL CHECK
        (status IN ('extracted','failed','skipped','deferred','pending')),
    reason text NOT NULL CHECK (length(reason) BETWEEN 1 AND 200),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    UNIQUE (tenant_id,parent_evidence_id,part_path),
    UNIQUE (tenant_id,evidence_id),
    FOREIGN KEY (tenant_id,parent_evidence_id) REFERENCES brain_evidence(tenant_id,id),
    FOREIGN KEY (tenant_id,evidence_id) REFERENCES brain_evidence(tenant_id,id)
);

CREATE TABLE brain_email_attachment_bridge_receipts (
    tenant_id uuid NOT NULL,
    actor_id uuid NOT NULL,
    idempotency_key uuid NOT NULL,
    account_id uuid NOT NULL,
    legacy_parent_version_id uuid NOT NULL,
    legacy_attachment_id uuid NOT NULL,
    parent_evidence_id text NOT NULL,
    source_id text NOT NULL CHECK (source_id ~ '^[a-z][a-z0-9_-]{0,127}$'),
    item_id text NOT NULL CHECK (item_id ~ '^[a-z][a-z0-9_-]{0,127}$'),
    version_id text NOT NULL CHECK (version_id ~ '^[a-z][a-z0-9_-]{0,127}$'),
    evidence_id text NOT NULL CHECK (evidence_id ~ '^[a-z][a-z0-9_-]{0,127}$'),
    part_id text NOT NULL CHECK (part_id ~ '^[a-z][a-z0-9_-]{0,127}$'),
    document_id text CHECK
        (document_id IS NULL OR document_id ~ '^[a-z][a-z0-9_-]{0,127}$'),
    chunk_count integer NOT NULL CHECK (chunk_count >= 0),
    outcome text NOT NULL CHECK
        (outcome IN ('extracted','failed','skipped','deferred','pending')),
    normalizer text CHECK (normalizer IS NULL OR length(normalizer) BETWEEN 1 AND 200),
    code_revision text NOT NULL CHECK (length(code_revision) BETWEEN 1 AND 200),
    request_hash text NOT NULL CHECK (request_hash ~ '^[a-f0-9]{64}$'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,actor_id,idempotency_key),
    UNIQUE (tenant_id,legacy_attachment_id),
    FOREIGN KEY (tenant_id,account_id,legacy_parent_version_id)
        REFERENCES message_versions(tenant_id,account_id,id),
    FOREIGN KEY (tenant_id,account_id,legacy_attachment_id)
        REFERENCES attachment_receipts(tenant_id,account_id,id),
    FOREIGN KEY (tenant_id,parent_evidence_id) REFERENCES brain_evidence(tenant_id,id),
    FOREIGN KEY (tenant_id,source_id,item_id,version_id)
        REFERENCES brain_source_versions(tenant_id,source_id,item_id,id),
    FOREIGN KEY (tenant_id,evidence_id) REFERENCES brain_evidence(tenant_id,id),
    FOREIGN KEY (tenant_id,part_id) REFERENCES brain_parts(tenant_id,id),
    FOREIGN KEY (tenant_id,document_id) REFERENCES brain_normalized_documents(tenant_id,id),
    CHECK (document_id IS NULL OR outcome='extracted'),
    CHECK ((document_id IS NULL)=(normalizer IS NULL)),
    CHECK ((document_id IS NULL AND chunk_count=0)
        OR (document_id IS NOT NULL AND chunk_count>0))
);

DO $block$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'brain_parts','brain_email_attachment_bridge_receipts'
    ] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',table_name);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',table_name);
        EXECUTE format('CREATE POLICY tenant_isolation ON %I USING
            (tenant_id=nullif(current_setting(''email_brain.tenant_id'',true),'''')::uuid)
            WITH CHECK
            (tenant_id=nullif(current_setting(''email_brain.tenant_id'',true),'''')::uuid)',table_name);
        EXECUTE format('CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON %I
            FOR EACH ROW EXECUTE FUNCTION deny_evidence_mutation()',table_name);
    END LOOP;
END $block$;

COMMIT;
