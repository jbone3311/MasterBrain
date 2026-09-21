BEGIN;

-- Generated provenance preserves old snapshots without rewriting immutable rows.
ALTER TABLE message_versions ADD COLUMN parser_version text
    GENERATED ALWAYS AS (snapshot->>'parser_version') STORED NOT NULL;
-- Older binaries could reuse a raw hash under another parser without a new
-- snapshot. Refuse silently hiding such projections; they need explicit repair.
DO $block$
BEGIN
    IF EXISTS (
        SELECT 1 FROM messages m JOIN message_versions v
        ON v.tenant_id=m.tenant_id AND v.message_id=m.id AND v.raw_sha256=m.raw_sha256
        WHERE m.parser_version <> v.parser_version
    ) THEN
        RAISE EXCEPTION 'parser provenance mismatch; explicit evidence repair required';
    END IF;
END $block$;
ALTER TABLE message_versions
    DROP CONSTRAINT message_versions_tenant_id_message_id_raw_sha256_key;
ALTER TABLE message_versions
    ADD UNIQUE (tenant_id,message_id,raw_sha256,parser_version);
ALTER TABLE quarantine_receipts ADD UNIQUE (tenant_id,account_id,id);
ALTER TABLE quarantine_receipts ADD COLUMN source_metadata jsonb;

CREATE TABLE recovery_attempts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    account_id uuid NOT NULL,
    receipt_id uuid NOT NULL,
    actor_id uuid NOT NULL,
    parser_version text NOT NULL CHECK (length(parser_version) BETWEEN 1 AND 100),
    outcome text NOT NULL CHECK (outcome IN ('recovered','mime_rejected','integrity_failed')),
    evidence_id uuid,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id,receipt_id,parser_version),
    FOREIGN KEY (tenant_id,account_id,receipt_id)
        REFERENCES quarantine_receipts(tenant_id,account_id,id),
    FOREIGN KEY (tenant_id,account_id,evidence_id)
        REFERENCES message_versions(tenant_id,account_id,id),
    CHECK ((outcome='recovered') = (evidence_id IS NOT NULL))
);
ALTER TABLE recovery_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE recovery_attempts FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON recovery_attempts
    USING (tenant_id = nullif(current_setting('email_brain.tenant_id',true),'')::uuid)
    WITH CHECK (tenant_id = nullif(current_setting('email_brain.tenant_id',true),'')::uuid);
CREATE TRIGGER recovery_attempts_immutable BEFORE UPDATE OR DELETE ON recovery_attempts
    FOR EACH ROW EXECUTE FUNCTION deny_evidence_mutation();

COMMIT;
