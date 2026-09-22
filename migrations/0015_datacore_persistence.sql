BEGIN;
CREATE TABLE brain_sources (
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    id text NOT NULL CHECK (id ~ '^[a-z][a-z0-9_-]{0,127}$'),
    kind text NOT NULL CHECK (kind IN ('email','fileos')),
    display_name text NOT NULL CHECK (length(display_name) BETWEEN 1 AND 200),
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','paused')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id)
);
CREATE TABLE brain_source_items (
    tenant_id uuid NOT NULL,
    source_id text NOT NULL,
    id text NOT NULL CHECK (id ~ '^[a-z][a-z0-9_-]{0,127}$'),
    locator text NOT NULL CHECK (length(locator) BETWEEN 1 AND 4000),
    current_version_id text,
    first_seen_at timestamptz NOT NULL,
    last_seen_at timestamptz NOT NULL CHECK (last_seen_at>=first_seen_at),
    PRIMARY KEY (tenant_id,id),
    UNIQUE (tenant_id,source_id,id),
    UNIQUE (tenant_id,source_id,locator),
    FOREIGN KEY (tenant_id,source_id) REFERENCES brain_sources(tenant_id,id)
);
CREATE TABLE brain_source_versions (
    tenant_id uuid NOT NULL,
    source_id text NOT NULL,
    item_id text NOT NULL,
    id text NOT NULL CHECK (id ~ '^[a-z][a-z0-9_-]{0,127}$'),
    observed_at timestamptz NOT NULL,
    sha256 text NOT NULL CHECK (sha256 ~ '^[a-f0-9]{64}$'),
    size_bytes bigint NOT NULL CHECK (size_bytes>=0),
    media_type text NOT NULL CHECK (length(media_type) BETWEEN 1 AND 200),
    metadata jsonb NOT NULL CHECK (jsonb_typeof(metadata)='object' AND octet_length(metadata::text)<=16000),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    UNIQUE (tenant_id,source_id,item_id,id),
    FOREIGN KEY (tenant_id,source_id,item_id) REFERENCES brain_source_items(tenant_id,source_id,id)
);
ALTER TABLE brain_source_items ADD CONSTRAINT brain_current_version
    FOREIGN KEY (tenant_id,source_id,id,current_version_id)
    REFERENCES brain_source_versions(tenant_id,source_id,item_id,id)
    DEFERRABLE INITIALLY DEFERRED;
CREATE INDEX brain_versions_by_source ON brain_source_versions(tenant_id,source_id,recorded_at,id);

CREATE TABLE brain_evidence (
    tenant_id uuid NOT NULL,
    id text NOT NULL CHECK (id ~ '^[a-z][a-z0-9_-]{0,127}$'),
    source_version_id text NOT NULL,
    sha256 text NOT NULL CHECK (sha256 ~ '^[a-f0-9]{64}$'),
    storage text NOT NULL CHECK (storage IN ('inline','object','source_bound')),
    retained boolean NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    UNIQUE (tenant_id,source_version_id),
    FOREIGN KEY (tenant_id,source_version_id) REFERENCES brain_source_versions(tenant_id,id),
    CHECK (storage<>'source_bound' OR NOT retained)
);
CREATE TABLE brain_normalized_documents (
    tenant_id uuid NOT NULL,
    id text NOT NULL CHECK (id ~ '^[a-z][a-z0-9_-]{0,127}$'),
    evidence_id text NOT NULL,
    normalizer text NOT NULL CHECK (length(normalizer) BETWEEN 1 AND 200),
    body_sha256 text NOT NULL CHECK (body_sha256 ~ '^[a-f0-9]{64}$'),
    body text NOT NULL CHECK (octet_length(body)<=1048576),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    UNIQUE (tenant_id,evidence_id,normalizer,body_sha256),
    FOREIGN KEY (tenant_id,evidence_id) REFERENCES brain_evidence(tenant_id,id)
);
CREATE TABLE brain_chunks (
    tenant_id uuid NOT NULL,
    id text NOT NULL CHECK (id ~ '^[a-z][a-z0-9_-]{0,127}$'),
    document_id text NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal>=0),
    start_offset integer NOT NULL CHECK (start_offset>=0),
    end_offset integer NOT NULL CHECK (end_offset>=start_offset),
    text text NOT NULL CHECK (length(text) BETWEEN 1 AND 2000),
    sha256 text NOT NULL CHECK (sha256 ~ '^[a-f0-9]{64}$'),
    search_vector tsvector GENERATED ALWAYS AS (to_tsvector('simple',text)) STORED,
    PRIMARY KEY (tenant_id,id),
    UNIQUE (tenant_id,document_id,ordinal),
    FOREIGN KEY (tenant_id,document_id) REFERENCES brain_normalized_documents(tenant_id,id)
);
CREATE INDEX brain_chunks_fts ON brain_chunks USING gin(search_vector);

CREATE TABLE brain_provenance (
    tenant_id uuid NOT NULL,
    id text NOT NULL CHECK (id ~ '^[a-z][a-z0-9_-]{0,127}$'),
    output_id text NOT NULL CHECK (output_id ~ '^[a-z][a-z0-9_-]{0,127}$'),
    transform text NOT NULL CHECK (length(transform) BETWEEN 1 AND 200),
    transform_version text NOT NULL CHECK (length(transform_version) BETWEEN 1 AND 200),
    code_revision text NOT NULL CHECK (length(code_revision) BETWEEN 1 AND 200),
    configuration_sha256 text NOT NULL CHECK (configuration_sha256 ~ '^[a-f0-9]{64}$'),
    created_at timestamptz NOT NULL,
    PRIMARY KEY (tenant_id,id)
);
CREATE TABLE brain_provenance_inputs (
    tenant_id uuid NOT NULL,
    provenance_id text NOT NULL,
    input_id text NOT NULL CHECK (input_id ~ '^[a-z][a-z0-9_-]{0,127}$'),
    ordinal integer NOT NULL CHECK (ordinal>=0),
    PRIMARY KEY (tenant_id,provenance_id,ordinal),
    UNIQUE (tenant_id,provenance_id,input_id),
    FOREIGN KEY (tenant_id,provenance_id) REFERENCES brain_provenance(tenant_id,id)
);
CREATE TABLE brain_change_events (
    tenant_id uuid NOT NULL,
    id text NOT NULL CHECK (id ~ '^[a-z][a-z0-9_-]{0,127}$'),
    source_id text NOT NULL,
    item_id text NOT NULL,
    version_id text NOT NULL,
    kind text NOT NULL CHECK (kind IN ('source_version_added','document_published')),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    FOREIGN KEY (tenant_id,source_id,item_id,version_id)
        REFERENCES brain_source_versions(tenant_id,source_id,item_id,id)
);
CREATE INDEX brain_changes_order ON brain_change_events(tenant_id,recorded_at,id);
CREATE TABLE brain_jobs (
    tenant_id uuid NOT NULL,
    id text NOT NULL CHECK (id ~ '^[a-z][a-z0-9_-]{0,127}$'),
    source_version_id text NOT NULL,
    kind text NOT NULL CHECK (kind IN ('extract','ocr','normalize','index')),
    status text NOT NULL CHECK (status IN ('queued','leased','succeeded','failed','deferred')),
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 20),
    available_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    lease_expires_at timestamptz,
    last_error_code text CHECK (last_error_code IS NULL OR length(last_error_code) BETWEEN 1 AND 100),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    FOREIGN KEY (tenant_id,source_version_id) REFERENCES brain_source_versions(tenant_id,id),
    CHECK ((status='leased')=(lease_expires_at IS NOT NULL))
);
CREATE INDEX brain_jobs_claim ON brain_jobs(tenant_id,status,available_at,created_at,id);
CREATE TABLE brain_import_receipts (
    tenant_id uuid NOT NULL,
    actor_id uuid NOT NULL,
    idempotency_key uuid NOT NULL,
    request_hash text NOT NULL CHECK (request_hash ~ '^[a-f0-9]{64}$'),
    result jsonb NOT NULL CHECK (jsonb_typeof(result)='object' AND octet_length(result::text)<=16000),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,actor_id,idempotency_key)
);

DO $block$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'brain_sources','brain_source_items','brain_source_versions','brain_evidence',
        'brain_normalized_documents','brain_chunks','brain_provenance',
        'brain_provenance_inputs','brain_change_events','brain_jobs','brain_import_receipts'
    ] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',table_name);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',table_name);
        EXECUTE format('CREATE POLICY tenant_isolation ON %I USING
            (tenant_id=nullif(current_setting(''email_brain.tenant_id'',true),'''')::uuid)
            WITH CHECK (tenant_id=nullif(current_setting(''email_brain.tenant_id'',true),'''')::uuid)',table_name);
    END LOOP;
    FOREACH table_name IN ARRAY ARRAY[
        'brain_source_versions','brain_evidence','brain_normalized_documents','brain_chunks',
        'brain_provenance','brain_provenance_inputs','brain_change_events','brain_import_receipts'
    ] LOOP
        EXECUTE format('CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON %I
            FOR EACH ROW EXECUTE FUNCTION deny_evidence_mutation()',table_name);
    END LOOP;
END $block$;
COMMIT;
