BEGIN;

ALTER TABLE raw_objects ALTER COLUMN raw_mime DROP NOT NULL;
ALTER TABLE raw_objects ADD COLUMN blob_ref jsonb;
ALTER TABLE raw_objects ADD COLUMN raw_size integer GENERATED ALWAYS AS (
    CASE WHEN raw_mime IS NOT NULL THEN octet_length(raw_mime)
         ELSE (blob_ref->>'byte_count')::integer END
) STORED NOT NULL;
ALTER TABLE raw_objects ADD CONSTRAINT raw_storage_choice
    CHECK ((raw_mime IS NULL) <> (blob_ref IS NULL));
ALTER TABLE raw_objects ADD CONSTRAINT raw_storage_size
    CHECK (raw_size BETWEEN 0 AND 16777216);
ALTER TABLE raw_objects ADD CONSTRAINT raw_manifest_valid CHECK (
    blob_ref IS NULL OR (
        jsonb_typeof(blob_ref)='object'
        AND blob_ref ?& ARRAY['object_key','sha256','byte_count','ciphertext_sha256','key_id']
        AND jsonb_typeof(blob_ref->'byte_count')='number'
        AND jsonb_typeof(blob_ref->'object_key')='string'
        AND jsonb_typeof(blob_ref->'sha256')='string'
        AND jsonb_typeof(blob_ref->'ciphertext_sha256')='string'
        AND jsonb_typeof(blob_ref->'key_id')='string'
        AND (blob_ref - 'object_key' - 'sha256' - 'byte_count'
             - 'ciphertext_sha256' - 'key_id') = '{}'::jsonb
        AND (blob_ref->>'sha256')=sha256
        AND (blob_ref->>'sha256') ~ '^[a-f0-9]{64}$'
        AND (blob_ref->>'ciphertext_sha256') ~ '^[a-f0-9]{64}$'
        AND (blob_ref->>'key_id') ~ '^[A-Za-z0-9_-]{1,64}$'
        AND (blob_ref->>'object_key') = 'v1/' || tenant_id::text || '/' ||
            account_id::text || '/' || (blob_ref->>'key_id') || '/' || sha256 || '.blob'
    )
);
ALTER TABLE quarantine_receipts DROP CONSTRAINT quarantine_receipts_reason_check;
ALTER TABLE quarantine_receipts ADD CONSTRAINT quarantine_receipts_reason_check
    CHECK (reason IN ('mime_rejected','mime_too_large'));

COMMIT;
