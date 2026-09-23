BEGIN;
CREATE FUNCTION valid_fileos_outcomes(jsonb,integer,integer) RETURNS boolean
LANGUAGE sql IMMUTABLE PARALLEL SAFE SET search_path=pg_catalog AS $function$
    SELECT jsonb_typeof($1)='object'
       AND NOT EXISTS (
           SELECT 1 FROM jsonb_each($1) AS entry(key,value)
           WHERE key <> ALL(ARRAY['extracted','empty','unsupported','deferred','changed','failed'])
              OR jsonb_typeof(value)<>'number'
              OR value::text !~ '^[1-9][0-9]*$'
       )
       AND COALESCE((
           SELECT sum(CASE WHEN value::text ~ '^[1-9][0-9]*$'
                           THEN (value #>> '{}')::integer ELSE 0 END)
           FROM jsonb_each($1)
       ),0)=$2
       AND CASE WHEN ($1->'extracted')::text ~ '^[1-9][0-9]*$'
                THEN ($1->>'extracted')::integer ELSE 0 END=$3
$function$;
CREATE TABLE brain_fileos_run_receipts (
    tenant_id uuid NOT NULL,
    actor_id uuid NOT NULL,
    run_id uuid NOT NULL,
    source_id text NOT NULL,
    observed_at timestamptz NOT NULL,
    manifest_sha256 text NOT NULL CHECK (manifest_sha256 ~ '^[a-f0-9]{64}$'),
    code_revision text NOT NULL CHECK (length(code_revision) BETWEEN 1 AND 200),
    text_extractor_version text NOT NULL CHECK (length(text_extractor_version) BETWEEN 1 AND 200),
    document_processor_version text CHECK (
        document_processor_version IS NULL OR length(document_processor_version) BETWEEN 1 AND 200
    ),
    item_count integer NOT NULL CHECK (item_count BETWEEN 0 AND 10000),
    outcomes jsonb NOT NULL CHECK (
        octet_length(outcomes::text)<=2000
        AND valid_fileos_outcomes(outcomes,item_count,published_documents)
    ),
    published_documents integer NOT NULL CHECK (published_documents BETWEEN 0 AND item_count),
    completed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,actor_id,run_id),
    FOREIGN KEY (tenant_id,source_id) REFERENCES brain_sources(tenant_id,id)
);
CREATE INDEX brain_fileos_runs_latest
    ON brain_fileos_run_receipts(tenant_id,source_id,completed_at DESC,run_id DESC);
ALTER TABLE brain_fileos_run_receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE brain_fileos_run_receipts FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON brain_fileos_run_receipts
    USING (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid)
    WITH CHECK (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid);
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON brain_fileos_run_receipts
    FOR EACH ROW EXECUTE FUNCTION deny_evidence_mutation();
COMMIT;
