BEGIN;

ALTER TABLE attachment_receipts ADD UNIQUE (tenant_id,account_id,id);
CREATE TRIGGER attachment_receipts_append_only BEFORE UPDATE OR DELETE ON attachment_receipts
    FOR EACH ROW EXECUTE FUNCTION deny_evidence_mutation();

CREATE FUNCTION document_page_text(payload jsonb) RETURNS text
LANGUAGE sql IMMUTABLE STRICT SET search_path=pg_catalog AS $function$
    SELECT coalesce(string_agg(p->>'text',E'\n' ORDER BY ord),'')
    FROM jsonb_array_elements(payload->'pages') WITH ORDINALITY AS pages(p,ord)
$function$;

CREATE TABLE document_extractions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    account_id uuid NOT NULL,
    receipt_id uuid NOT NULL,
    processor_version text NOT NULL CHECK (processor_version ~ '^sandbox-pdf-v1-[a-f0-9]{64}$'),
    policy_version text NOT NULL CHECK (policy_version='synthetic-unscanned-pdf-v1'),
    revision integer NOT NULL CHECK (revision>0),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    result jsonb NOT NULL CHECK (octet_length(result::text)<=1048576),
    status text GENERATED ALWAYS AS (result->>'status') STORED NOT NULL,
    reason text GENERATED ALWAYS AS (result->>'reason') STORED NOT NULL,
    scanner_status text GENERATED ALWAYS AS (result->>'scanner_status') STORED NOT NULL,
    extracted_text text GENERATED ALWAYS AS (document_page_text(result)) STORED NOT NULL,
    search_document tsvector GENERATED ALWAYS AS
        (to_tsvector('simple',document_page_text(result))) STORED,
    UNIQUE (tenant_id,account_id,receipt_id,processor_version,policy_version),
    UNIQUE (tenant_id,account_id,receipt_id,revision),
    UNIQUE (tenant_id,account_id,receipt_id,processor_version,policy_version,id),
    FOREIGN KEY (tenant_id,account_id,receipt_id)
        REFERENCES attachment_receipts(tenant_id,account_id,id),
    CHECK (status IN ('extracted','partial','deferred','failed')),
    CHECK (scanner_status='unscanned'),
    CHECK (result->>'contract_version'='sandbox-pdf-v1'),
    CHECK (jsonb_typeof(result->'pages')='array'),
    CHECK (jsonb_array_length(result->'pages')<=40),
    CHECK (length(extracted_text)<=100039),
    CHECK ((status IN ('extracted','partial')) = (length(extracted_text)>0))
);
CREATE INDEX document_extractions_fts ON document_extractions USING gin(search_document);
CREATE FUNCTION validate_document_source() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM public.attachment_receipts a JOIN public.message_versions v
          ON v.tenant_id=a.tenant_id AND v.account_id=a.account_id AND v.id=a.evidence_id
        WHERE a.tenant_id=NEW.tenant_id AND a.account_id=NEW.account_id AND a.id=NEW.receipt_id
          AND NEW.result->'source'=jsonb_build_object('raw_sha256',v.raw_sha256,
              'part_path',a.part_id,'part_sha256',a.sha256)
    ) THEN RAISE EXCEPTION 'document source mismatch'; END IF;
    RETURN NEW;
END $function$;
CREATE TRIGGER document_source BEFORE INSERT ON document_extractions
    FOR EACH ROW EXECUTE FUNCTION validate_document_source();
CREATE TRIGGER document_extractions_append_only BEFORE UPDATE OR DELETE ON document_extractions
    FOR EACH ROW EXECUTE FUNCTION deny_evidence_mutation();

CREATE TABLE document_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    account_id uuid NOT NULL,
    receipt_id uuid NOT NULL,
    source_event_key text NOT NULL,
    actor_id uuid NOT NULL,
    idempotency_key uuid NOT NULL,
    processor_version text NOT NULL CHECK (processor_version ~ '^sandbox-pdf-v1-[a-f0-9]{64}$'),
    policy_version text NOT NULL CHECK (policy_version='synthetic-unscanned-pdf-v1'),
    created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
    expires_at timestamptz NOT NULL DEFAULT statement_timestamp()+interval '1 hour',
    status text NOT NULL DEFAULT 'queued' CHECK (status IN
        ('queued','running','retry_wait','completed','cancelled','expired','failed','stale','revoked')),
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 3),
    lease_token uuid,
    lease_until timestamptz,
    worker_actor_id uuid,
    retry_at timestamptz,
    completed_at timestamptz,
    extraction_id uuid,
    outcome text CHECK (outcome IN ('result_saved','cancelled','approval_expired',
        'attempts_exhausted','infrastructure_unavailable','authorization_revoked','source_changed')),
    UNIQUE (tenant_id,actor_id,idempotency_key),
    FOREIGN KEY (tenant_id,account_id,receipt_id)
        REFERENCES attachment_receipts(tenant_id,account_id,id),
    FOREIGN KEY (tenant_id,account_id,receipt_id,processor_version,policy_version,extraction_id)
        REFERENCES document_extractions(tenant_id,account_id,receipt_id,processor_version,policy_version,id),
    CHECK (expires_at=created_at+interval '1 hour'),
    CHECK ((status='running')=(lease_token IS NOT NULL AND lease_until IS NOT NULL)),
    CHECK (status='running' OR (lease_token IS NULL AND lease_until IS NULL)),
    CHECK (status<>'running' OR (worker_actor_id IS NOT NULL AND attempts>0 AND retry_at IS NULL)),
    CHECK (status<>'queued' OR (attempts=0 AND worker_actor_id IS NULL AND retry_at IS NULL)),
    CHECK ((status='retry_wait')=(retry_at IS NOT NULL)),
    CHECK (status<>'retry_wait' OR attempts BETWEEN 1 AND 2),
    CHECK ((status='completed')=(extraction_id IS NOT NULL)),
    CHECK ((status IN ('completed','cancelled','expired','failed','stale','revoked'))
        =(completed_at IS NOT NULL)),
    CHECK (CASE status
        WHEN 'queued' THEN outcome IS NULL
        WHEN 'running' THEN outcome IS NULL
        WHEN 'completed' THEN outcome='result_saved'
        WHEN 'retry_wait' THEN outcome='infrastructure_unavailable'
        WHEN 'failed' THEN outcome IN ('attempts_exhausted','infrastructure_unavailable')
        WHEN 'cancelled' THEN outcome='cancelled'
        WHEN 'expired' THEN outcome='approval_expired'
        WHEN 'revoked' THEN outcome='authorization_revoked'
        WHEN 'stale' THEN outcome='source_changed'
        ELSE false END),
    CHECK (status IN ('queued','running') OR outcome IS NOT NULL)
);
CREATE INDEX document_jobs_queue ON document_jobs(tenant_id,account_id,created_at,id)
    WHERE status IN ('queued','running','retry_wait');
CREATE INDEX document_jobs_history ON document_jobs(tenant_id,account_id,created_at DESC,id DESC);

CREATE FUNCTION protect_document_job() RETURNS trigger LANGUAGE plpgsql AS $function$
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'document approval is retained'; END IF;
    IF (NEW.id,NEW.tenant_id,NEW.account_id,NEW.receipt_id,NEW.source_event_key,NEW.actor_id,
        NEW.idempotency_key,NEW.processor_version,NEW.policy_version,NEW.created_at,NEW.expires_at)
       IS DISTINCT FROM
       (OLD.id,OLD.tenant_id,OLD.account_id,OLD.receipt_id,OLD.source_event_key,OLD.actor_id,
        OLD.idempotency_key,OLD.processor_version,OLD.policy_version,OLD.created_at,OLD.expires_at)
    THEN RAISE EXCEPTION 'document approval is immutable'; END IF;
    IF OLD.status IN ('completed','cancelled','expired','failed','stale','revoked') THEN
        IF NEW IS DISTINCT FROM OLD THEN RAISE EXCEPTION 'document terminal state is immutable'; END IF;
        RETURN NEW;
    END IF;
    IF NEW.status='running' THEN
        IF NEW.attempts<>OLD.attempts+1 OR NEW.lease_token IS NULL
           OR NEW.lease_token IS NOT DISTINCT FROM OLD.lease_token
           OR (OLD.status='running' AND OLD.lease_until>clock_timestamp())
           OR (OLD.status='retry_wait' AND OLD.retry_at>clock_timestamp())
        THEN RAISE EXCEPTION 'invalid document claim'; END IF;
    ELSIF NEW.attempts<>OLD.attempts THEN RAISE EXCEPTION 'document claims cannot be rewritten';
    END IF;
    IF NEW.status='queued' OR (NEW.status IN ('completed','retry_wait') AND OLD.status<>'running')
    THEN RAISE EXCEPTION 'invalid document transition'; END IF;
    RETURN NEW;
END $function$;
CREATE TRIGGER document_jobs_protected BEFORE UPDATE OR DELETE ON document_jobs
    FOR EACH ROW EXECUTE FUNCTION protect_document_job();

DO $block$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY['document_jobs','document_extractions'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',table_name);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',table_name);
        EXECUTE format('CREATE POLICY tenant_isolation ON %I USING
            (tenant_id=nullif(current_setting(''email_brain.tenant_id'',true),'''')::uuid)
            WITH CHECK (tenant_id=nullif(current_setting(''email_brain.tenant_id'',true),'''')::uuid)',table_name);
    END LOOP;
END $block$;
COMMIT;
