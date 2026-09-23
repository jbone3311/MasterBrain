BEGIN;

CREATE TABLE brain_archive_member_image_receipts (
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
    image_processor text NOT NULL CHECK (
        image_processor ~ '^sandbox-fileos-image-ocr-v1-[a-f0-9]{64}$'
    ),
    image_format text NOT NULL CHECK (
        image_format IN ('jpeg','png','tiff','bmp','gif','webp')
    ),
    detected_format text NOT NULL CHECK (
        detected_format=image_format AND
        detected_format IN ('jpeg','png','tiff','bmp','gif','webp')
    ),
    width integer NOT NULL CHECK (width BETWEEN 1 AND 25000000),
    height integer NOT NULL CHECK (
        height BETWEEN 1 AND 25000000 AND width::bigint*height::bigint<=25000000
    ),
    mode text NOT NULL CHECK (length(mode) BETWEEN 1 AND 16),
    frame_count integer NOT NULL CHECK (frame_count=1),
    truncated boolean NOT NULL,
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

ALTER TABLE brain_archive_member_image_receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE brain_archive_member_image_receipts FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON brain_archive_member_image_receipts USING
    (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid)
    WITH CHECK
    (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid);
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON brain_archive_member_image_receipts
    FOR EACH ROW EXECUTE FUNCTION deny_evidence_mutation();

COMMIT;
