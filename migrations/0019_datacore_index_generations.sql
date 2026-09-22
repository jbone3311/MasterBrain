BEGIN;
ALTER TABLE brain_evidence ADD CONSTRAINT brain_evidence_id_version_unique
    UNIQUE (tenant_id,id,source_version_id);
ALTER TABLE brain_normalized_documents ADD CONSTRAINT brain_document_id_evidence_unique
    UNIQUE (tenant_id,id,evidence_id);

CREATE TABLE brain_index_generations (
    tenant_id uuid NOT NULL,
    id text NOT NULL CHECK (id ~ '^[a-z][a-z0-9_-]{0,127}$'),
    source_id text NOT NULL,
    run_actor_id uuid NOT NULL,
    run_id uuid NOT NULL,
    observed_at timestamptz NOT NULL,
    plan_sha256 text NOT NULL CHECK (plan_sha256 ~ '^[a-f0-9]{64}$'),
    code_revision text NOT NULL CHECK (length(code_revision) BETWEEN 1 AND 200),
    chunker_version text NOT NULL CHECK (length(chunker_version) BETWEEN 1 AND 200),
    item_count integer NOT NULL CHECK (item_count BETWEEN 0 AND 10000),
    document_count integer NOT NULL CHECK (document_count BETWEEN 0 AND item_count),
    chunk_count integer NOT NULL CHECK (chunk_count BETWEEN 0 AND 100000),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    UNIQUE (tenant_id,id,source_id),
    UNIQUE (tenant_id,source_id,run_actor_id,run_id,plan_sha256),
    FOREIGN KEY (tenant_id,run_actor_id,run_id,source_id,observed_at)
        REFERENCES brain_fileos_run_receipts(
            tenant_id,actor_id,run_id,source_id,observed_at
        )
);

CREATE TABLE brain_index_generation_items (
    tenant_id uuid NOT NULL,
    generation_id text NOT NULL,
    source_id text NOT NULL,
    item_id text NOT NULL,
    version_id text NOT NULL,
    outcome text NOT NULL CHECK (
        outcome IN ('extracted','empty','unsupported','deferred','changed','failed')
    ),
    disposition text NOT NULL CHECK (disposition IN ('indexed','not_indexed')),
    evidence_id text NOT NULL,
    document_id text,
    PRIMARY KEY (tenant_id,generation_id,item_id),
    UNIQUE (tenant_id,generation_id,source_id,item_id),
    UNIQUE (tenant_id,generation_id,source_id,document_id),
    FOREIGN KEY (tenant_id,generation_id,source_id)
        REFERENCES brain_index_generations(tenant_id,id,source_id),
    FOREIGN KEY (tenant_id,source_id,item_id,version_id)
        REFERENCES brain_source_versions(tenant_id,source_id,item_id,id),
    FOREIGN KEY (tenant_id,evidence_id,version_id)
        REFERENCES brain_evidence(tenant_id,id,source_version_id),
    FOREIGN KEY (tenant_id,document_id,evidence_id)
        REFERENCES brain_normalized_documents(tenant_id,id,evidence_id),
    CHECK ((disposition='indexed')=(document_id IS NOT NULL))
);

CREATE TABLE brain_index_generation_chunks (
    tenant_id uuid NOT NULL,
    generation_id text NOT NULL,
    source_id text NOT NULL,
    document_id text NOT NULL,
    id text NOT NULL CHECK (id ~ '^[a-z][a-z0-9_-]{0,127}$'),
    ordinal integer NOT NULL CHECK (ordinal>=0),
    start_offset integer NOT NULL CHECK (start_offset>=0),
    end_offset integer NOT NULL CHECK (end_offset>=start_offset),
    text text NOT NULL CHECK (length(text) BETWEEN 1 AND 2000),
    sha256 text NOT NULL CHECK (sha256 ~ '^[a-f0-9]{64}$'),
    search_vector tsvector GENERATED ALWAYS AS (to_tsvector('simple',text)) STORED,
    PRIMARY KEY (tenant_id,generation_id,id),
    UNIQUE (tenant_id,generation_id,document_id,ordinal),
    FOREIGN KEY (tenant_id,generation_id,source_id,document_id)
        REFERENCES brain_index_generation_items(
            tenant_id,generation_id,source_id,document_id
        )
);
CREATE INDEX brain_index_generation_chunks_fts
    ON brain_index_generation_chunks USING gin(search_vector);

CREATE TABLE brain_index_generation_receipts (
    tenant_id uuid NOT NULL,
    generation_id text NOT NULL,
    source_id text NOT NULL,
    ready_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,generation_id),
    UNIQUE (tenant_id,generation_id,source_id),
    FOREIGN KEY (tenant_id,generation_id,source_id)
        REFERENCES brain_index_generations(tenant_id,id,source_id)
);

CREATE TABLE brain_index_activations (
    tenant_id uuid NOT NULL,
    actor_id uuid NOT NULL,
    idempotency_key uuid NOT NULL,
    source_id text NOT NULL,
    generation_id text NOT NULL,
    previous_generation_id text,
    request_hash text NOT NULL CHECK (request_hash ~ '^[a-f0-9]{64}$'),
    activated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,actor_id,idempotency_key),
    FOREIGN KEY (tenant_id,generation_id,source_id)
        REFERENCES brain_index_generation_receipts(tenant_id,generation_id,source_id),
    FOREIGN KEY (tenant_id,previous_generation_id,source_id)
        REFERENCES brain_index_generation_receipts(tenant_id,generation_id,source_id)
);
CREATE INDEX brain_index_activations_latest
    ON brain_index_activations(tenant_id,source_id,activated_at DESC,idempotency_key DESC);

CREATE FUNCTION enforce_index_generation_ready() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
DECLARE
    expected_items integer;
    expected_documents integer;
    expected_chunks integer;
    actual_items integer;
    actual_documents integer;
    actual_chunks integer;
    documents_without_chunks integer;
BEGIN
    SELECT item_count,document_count,chunk_count
    INTO expected_items,expected_documents,expected_chunks
    FROM public.brain_index_generations
    WHERE tenant_id=NEW.tenant_id AND id=NEW.generation_id AND source_id=NEW.source_id;
    SELECT count(*)::integer,count(document_id)::integer
    INTO actual_items,actual_documents
    FROM public.brain_index_generation_items
    WHERE tenant_id=NEW.tenant_id AND generation_id=NEW.generation_id;
    SELECT count(*)::integer INTO actual_chunks
    FROM public.brain_index_generation_chunks
    WHERE tenant_id=NEW.tenant_id AND generation_id=NEW.generation_id;
    SELECT count(*)::integer INTO documents_without_chunks
    FROM public.brain_index_generation_items i
    WHERE i.tenant_id=NEW.tenant_id AND i.generation_id=NEW.generation_id
      AND i.document_id IS NOT NULL AND NOT EXISTS (
          SELECT 1 FROM public.brain_index_generation_chunks c
          WHERE c.tenant_id=i.tenant_id AND c.generation_id=i.generation_id
            AND c.document_id=i.document_id
      );
    IF expected_items IS NULL OR actual_items<>expected_items
       OR actual_documents<>expected_documents OR actual_chunks<>expected_chunks
       OR documents_without_chunks<>0 THEN
        RAISE EXCEPTION 'index generation is not complete';
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER index_generation_ready
    BEFORE INSERT ON brain_index_generation_receipts
    FOR EACH ROW EXECUTE FUNCTION enforce_index_generation_ready();

CREATE FUNCTION deny_ready_generation_append() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
BEGIN
    IF EXISTS (
        SELECT 1 FROM public.brain_index_generation_receipts
        WHERE tenant_id=NEW.tenant_id AND generation_id=NEW.generation_id
    ) THEN
        RAISE EXCEPTION 'ready index generation is immutable';
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER generation_items_closed BEFORE INSERT ON brain_index_generation_items
    FOR EACH ROW EXECUTE FUNCTION deny_ready_generation_append();
CREATE TRIGGER generation_chunks_closed BEFORE INSERT ON brain_index_generation_chunks
    FOR EACH ROW EXECUTE FUNCTION deny_ready_generation_append();

DO $block$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'brain_index_generations','brain_index_generation_items',
        'brain_index_generation_chunks','brain_index_generation_receipts',
        'brain_index_activations'
    ] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',table_name);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',table_name);
        EXECUTE format('CREATE POLICY tenant_isolation ON %I USING
            (tenant_id=nullif(current_setting(''email_brain.tenant_id'',true),'''')::uuid)
            WITH CHECK (tenant_id=nullif(current_setting(''email_brain.tenant_id'',true),'''')::uuid)',table_name);
        EXECUTE format('CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON %I
            FOR EACH ROW EXECUTE FUNCTION deny_evidence_mutation()',table_name);
    END LOOP;
END $block$;
COMMIT;
