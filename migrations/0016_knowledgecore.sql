BEGIN;
CREATE TABLE knowledge_entities (
    tenant_id uuid NOT NULL,
    id text NOT NULL CHECK (id ~ '^entity_[a-f0-9]{32}$'),
    entity_type text NOT NULL CHECK (entity_type IN ('person','organization','place','account','artifact','other')),
    name text NOT NULL CHECK (length(name) BETWEEN 1 AND 300),
    confidence double precision NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    source_quote text NOT NULL CHECK (length(source_quote) BETWEEN 1 AND 2000),
    observed_at timestamptz NOT NULL,
    valid_from timestamptz,
    valid_to timestamptz,
    supersedes_id text,
    reviewer_id uuid NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    FOREIGN KEY (tenant_id,supersedes_id) REFERENCES knowledge_entities(tenant_id,id),
    CHECK (valid_to IS NULL OR valid_from IS NOT NULL),
    CHECK (valid_to IS NULL OR valid_to>valid_from)
);
CREATE TABLE knowledge_entity_aliases (
    tenant_id uuid NOT NULL,
    id text NOT NULL CHECK (id ~ '^alias_[a-f0-9]{32}$'),
    entity_id text NOT NULL,
    alias text NOT NULL CHECK (length(alias) BETWEEN 1 AND 300),
    normalized_alias text NOT NULL CHECK (length(normalized_alias) BETWEEN 1 AND 300),
    PRIMARY KEY (tenant_id,id),
    UNIQUE (tenant_id,entity_id,normalized_alias),
    FOREIGN KEY (tenant_id,entity_id) REFERENCES knowledge_entities(tenant_id,id)
);
CREATE TABLE knowledge_relationships (
    tenant_id uuid NOT NULL,
    id text NOT NULL CHECK (id ~ '^relationship_[a-f0-9]{32}$'),
    subject_entity_id text NOT NULL,
    predicate text NOT NULL CHECK (predicate ~ '^[a-z][a-z0-9_.-]{0,99}$'),
    object_entity_id text NOT NULL,
    assertion_status text NOT NULL CHECK (assertion_status IN ('asserted','disputed','retracted')),
    confidence double precision NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    source_quote text NOT NULL CHECK (length(source_quote) BETWEEN 1 AND 2000),
    observed_at timestamptz NOT NULL,
    valid_from timestamptz,
    valid_to timestamptz,
    supersedes_id text,
    reviewer_id uuid NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    FOREIGN KEY (tenant_id,subject_entity_id) REFERENCES knowledge_entities(tenant_id,id),
    FOREIGN KEY (tenant_id,object_entity_id) REFERENCES knowledge_entities(tenant_id,id),
    FOREIGN KEY (tenant_id,supersedes_id) REFERENCES knowledge_relationships(tenant_id,id),
    CHECK (subject_entity_id<>object_entity_id),
    CHECK (valid_to IS NULL OR (valid_from IS NOT NULL AND valid_to>valid_from))
);
CREATE TABLE knowledge_claims (
    tenant_id uuid NOT NULL,
    id text NOT NULL CHECK (id ~ '^claim_[a-f0-9]{32}$'),
    subject_entity_id text NOT NULL,
    predicate text NOT NULL CHECK (predicate ~ '^[a-z][a-z0-9_.-]{0,99}$'),
    value text NOT NULL CHECK (length(value) BETWEEN 1 AND 4000),
    value_type text NOT NULL CHECK (value_type IN ('text','number','date','boolean','reference')),
    assertion_status text NOT NULL CHECK (assertion_status IN ('asserted','disputed','retracted')),
    confidence double precision NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    source_quote text NOT NULL CHECK (length(source_quote) BETWEEN 1 AND 2000),
    observed_at timestamptz NOT NULL,
    valid_from timestamptz,
    valid_to timestamptz,
    supersedes_id text,
    reviewer_id uuid NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    FOREIGN KEY (tenant_id,subject_entity_id) REFERENCES knowledge_entities(tenant_id,id),
    FOREIGN KEY (tenant_id,supersedes_id) REFERENCES knowledge_claims(tenant_id,id),
    CHECK (valid_to IS NULL OR (valid_from IS NOT NULL AND valid_to>valid_from))
);
CREATE TABLE knowledge_projects (
    tenant_id uuid NOT NULL,
    id text NOT NULL CHECK (id ~ '^project_[a-f0-9]{32}$'),
    title text NOT NULL CHECK (length(title) BETWEEN 1 AND 300),
    description text NOT NULL CHECK (length(description)<=4000),
    state text NOT NULL CHECK (state IN ('proposed','active','blocked','completed','cancelled','unknown')),
    confidence double precision NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    source_quote text NOT NULL CHECK (length(source_quote) BETWEEN 1 AND 2000),
    observed_at timestamptz NOT NULL,
    valid_from timestamptz,
    valid_to timestamptz,
    supersedes_id text,
    reviewer_id uuid NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    FOREIGN KEY (tenant_id,supersedes_id) REFERENCES knowledge_projects(tenant_id,id),
    CHECK (valid_to IS NULL OR (valid_from IS NOT NULL AND valid_to>valid_from))
);
CREATE TABLE knowledge_events (
    tenant_id uuid NOT NULL,
    id text NOT NULL CHECK (id ~ '^event_[a-f0-9]{32}$'),
    event_type text NOT NULL CHECK (event_type ~ '^[a-z][a-z0-9_.-]{0,99}$'),
    title text NOT NULL CHECK (length(title) BETWEEN 1 AND 300),
    description text NOT NULL CHECK (length(description)<=4000),
    starts_at timestamptz,
    ends_at timestamptz,
    project_id text,
    confidence double precision NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    source_quote text NOT NULL CHECK (length(source_quote) BETWEEN 1 AND 2000),
    observed_at timestamptz NOT NULL,
    valid_from timestamptz,
    valid_to timestamptz,
    supersedes_id text,
    reviewer_id uuid NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    FOREIGN KEY (tenant_id,project_id) REFERENCES knowledge_projects(tenant_id,id),
    FOREIGN KEY (tenant_id,supersedes_id) REFERENCES knowledge_events(tenant_id,id),
    CHECK (ends_at IS NULL OR (starts_at IS NOT NULL AND ends_at>starts_at)),
    CHECK (valid_to IS NULL OR (valid_from IS NOT NULL AND valid_to>valid_from))
);
CREATE TABLE knowledge_commitments (
    tenant_id uuid NOT NULL,
    id text NOT NULL CHECK (id ~ '^commitment_[a-f0-9]{32}$'),
    description text NOT NULL CHECK (length(description) BETWEEN 1 AND 4000),
    state text NOT NULL CHECK (state IN ('proposed','open','completed','cancelled','overdue','unknown')),
    owner_entity_id text,
    counterparty_entity_id text,
    project_id text,
    due_at timestamptz,
    confidence double precision NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    source_quote text NOT NULL CHECK (length(source_quote) BETWEEN 1 AND 2000),
    observed_at timestamptz NOT NULL,
    valid_from timestamptz,
    valid_to timestamptz,
    supersedes_id text,
    reviewer_id uuid NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    FOREIGN KEY (tenant_id,owner_entity_id) REFERENCES knowledge_entities(tenant_id,id),
    FOREIGN KEY (tenant_id,counterparty_entity_id) REFERENCES knowledge_entities(tenant_id,id),
    FOREIGN KEY (tenant_id,project_id) REFERENCES knowledge_projects(tenant_id,id),
    FOREIGN KEY (tenant_id,supersedes_id) REFERENCES knowledge_commitments(tenant_id,id),
    CHECK (valid_to IS NULL OR (valid_from IS NOT NULL AND valid_to>valid_from))
);
CREATE TABLE knowledge_corrections (
    tenant_id uuid NOT NULL,
    id text NOT NULL CHECK (id ~ '^correction_[a-f0-9]{32}$'),
    target_kind text NOT NULL CHECK (target_kind IN ('entity','relationship','claim','event','project','commitment')),
    target_id text NOT NULL CHECK (target_id ~ '^[a-z]+_[a-f0-9]{32}$'),
    replacement_id text NOT NULL CHECK (replacement_id ~ '^[a-z]+_[a-f0-9]{32}$'),
    reason text NOT NULL CHECK (length(reason) BETWEEN 1 AND 2000),
    source_quote text NOT NULL CHECK (length(source_quote) BETWEEN 1 AND 2000),
    observed_at timestamptz NOT NULL,
    reviewer_id uuid NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    CHECK (target_id<>replacement_id)
);
CREATE TABLE knowledge_evidence (
    tenant_id uuid NOT NULL,
    target_kind text NOT NULL CHECK (target_kind IN ('entity','relationship','claim','event','project','commitment','correction')),
    target_id text NOT NULL CHECK (target_id ~ '^[a-z]+_[a-f0-9]{32}$'),
    evidence_id text NOT NULL,
    stance text NOT NULL CHECK (stance IN ('supports','contradicts','context')),
    locator jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(locator)='object' AND octet_length(locator::text)<=2000),
    PRIMARY KEY (tenant_id,target_kind,target_id,evidence_id),
    FOREIGN KEY (tenant_id,evidence_id) REFERENCES brain_evidence(tenant_id,id)
);
CREATE TABLE knowledge_search_documents (
    tenant_id uuid NOT NULL,
    object_kind text NOT NULL CHECK (object_kind IN ('entity','relationship','claim','event','project','commitment','correction')),
    object_id text NOT NULL CHECK (object_id ~ '^[a-z]+_[a-f0-9]{32}$'),
    title text NOT NULL CHECK (length(title) BETWEEN 1 AND 500),
    body text NOT NULL CHECK (length(body) BETWEEN 1 AND 8000),
    search_vector tsvector GENERATED ALWAYS AS (setweight(to_tsvector('simple',title),'A') || setweight(to_tsvector('simple',body),'B')) STORED,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,object_kind,object_id)
);
CREATE INDEX knowledge_search_fts ON knowledge_search_documents USING gin(search_vector);
CREATE TABLE knowledge_change_events (
    tenant_id uuid NOT NULL,
    id text NOT NULL CHECK (id ~ '^kchange_[a-f0-9]{32}$'),
    object_kind text NOT NULL,
    object_id text NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id)
);
CREATE INDEX knowledge_changes_order ON knowledge_change_events(tenant_id,recorded_at,id);
CREATE TABLE knowledge_receipts (
    tenant_id uuid NOT NULL,
    actor_id uuid NOT NULL,
    idempotency_key uuid NOT NULL,
    request_hash text NOT NULL CHECK (request_hash ~ '^[a-f0-9]{64}$'),
    object_kind text NOT NULL,
    object_id text NOT NULL,
    PRIMARY KEY (tenant_id,actor_id,idempotency_key)
);

DO $block$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'knowledge_entities','knowledge_entity_aliases','knowledge_relationships',
        'knowledge_claims','knowledge_projects','knowledge_events','knowledge_commitments',
        'knowledge_corrections','knowledge_evidence','knowledge_search_documents',
        'knowledge_change_events','knowledge_receipts'
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
