-- Additive prototype schema. Execute as migration owner, never runtime.
BEGIN;

ALTER TABLE mail_accounts ADD UNIQUE (tenant_id, id);
ALTER TABLE sync_cursors DROP CONSTRAINT sync_cursors_account_id_fkey;
ALTER TABLE sync_cursors ADD FOREIGN KEY (tenant_id, account_id)
    REFERENCES mail_accounts(tenant_id, id);
ALTER TABLE provider_events DROP CONSTRAINT provider_events_account_id_fkey;
ALTER TABLE provider_events ADD FOREIGN KEY (tenant_id, account_id)
    REFERENCES mail_accounts(tenant_id, id);
ALTER TABLE provider_events ADD COLUMN event_hash text;

ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenants FORCE ROW LEVEL SECURITY;
CREATE POLICY tenants_isolation ON tenants
    USING (id = nullif(current_setting('email_brain.tenant_id', true), '')::uuid)
    WITH CHECK (id = nullif(current_setting('email_brain.tenant_id', true), '')::uuid);

CREATE TABLE raw_objects (
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    account_id uuid NOT NULL,
    sha256 text NOT NULL CHECK (length(sha256) = 64),
    raw_mime bytea NOT NULL CHECK (octet_length(raw_mime) <= 1048576),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, account_id, sha256),
    FOREIGN KEY (tenant_id, account_id) REFERENCES mail_accounts(tenant_id, id)
);

CREATE TABLE messages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    account_id uuid NOT NULL,
    provider_message_id text NOT NULL,
    provider_version text NOT NULL,
    provider_thread_id text,
    internet_message_id text,
    subject text NOT NULL,
    sender text NOT NULL,
    recipients jsonb NOT NULL,
    clean_text text NOT NULL,
    raw_sha256 text NOT NULL,
    parser_version text NOT NULL,
    received_at timestamptz NOT NULL,
    deleted boolean NOT NULL DEFAULT false,
    search_document tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('simple', subject), 'A') ||
        setweight(to_tsvector('simple', sender), 'B') ||
        setweight(to_tsvector('simple', clean_text), 'C')
    ) STORED,
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, account_id, provider_message_id),
    UNIQUE (tenant_id, id),
    FOREIGN KEY (tenant_id, account_id) REFERENCES mail_accounts(tenant_id, id),
    FOREIGN KEY (tenant_id, account_id, raw_sha256)
        REFERENCES raw_objects(tenant_id, account_id, sha256)
);
CREATE INDEX messages_fts ON messages USING gin(search_document);
CREATE INDEX messages_account_time ON messages(tenant_id, account_id, received_at DESC);

CREATE TABLE message_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    account_id uuid NOT NULL,
    message_id uuid NOT NULL,
    raw_sha256 text NOT NULL,
    provider_version text NOT NULL,
    snapshot jsonb NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, message_id, raw_sha256),
    FOREIGN KEY (tenant_id, message_id) REFERENCES messages(tenant_id, id),
    FOREIGN KEY (tenant_id, account_id, raw_sha256)
        REFERENCES raw_objects(tenant_id, account_id, sha256)
);

CREATE TABLE proposals (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    actor_id uuid NOT NULL,
    idempotency_key uuid NOT NULL,
    request_hash text NOT NULL,
    kind text NOT NULL CHECK (kind IN ('rule', 'project', 'fact', 'feature', 'correction')),
    payload jsonb NOT NULL,
    reason text NOT NULL,
    source text NOT NULL,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    version integer NOT NULL DEFAULT 1,
    reviewed_by uuid,
    reviewed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, actor_id, idempotency_key),
    UNIQUE (tenant_id, id)
);
CREATE TABLE proposal_evidence (
    tenant_id uuid NOT NULL,
    proposal_id uuid NOT NULL,
    evidence_id uuid NOT NULL,
    PRIMARY KEY (tenant_id, proposal_id, evidence_id),
    FOREIGN KEY (tenant_id, proposal_id) REFERENCES proposals(tenant_id, id),
    FOREIGN KEY (tenant_id, evidence_id) REFERENCES message_versions(tenant_id, id)
);

DO $block$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'raw_objects', 'messages', 'message_versions', 'proposals', 'proposal_evidence'
    ]
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', table_name);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', table_name);
        EXECUTE format(
            'CREATE POLICY tenant_isolation ON %I USING
             (tenant_id = nullif(current_setting(''email_brain.tenant_id'', true), '''')::uuid)
             WITH CHECK
             (tenant_id = nullif(current_setting(''email_brain.tenant_id'', true), '''')::uuid)',
            table_name
        );
    END LOOP;
END $block$;

CREATE FUNCTION deny_evidence_mutation() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
    RAISE EXCEPTION 'append-only record; retention requires a separately authorized maintenance path';
END $body$;
CREATE TRIGGER audit_append_only BEFORE UPDATE OR DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION deny_evidence_mutation();
CREATE TRIGGER raw_append_only BEFORE UPDATE OR DELETE ON raw_objects
    FOR EACH ROW EXECUTE FUNCTION deny_evidence_mutation();
CREATE TRIGGER events_append_only BEFORE UPDATE OR DELETE ON provider_events
    FOR EACH ROW EXECUTE FUNCTION deny_evidence_mutation();
CREATE TRIGGER versions_append_only BEFORE UPDATE OR DELETE ON message_versions
    FOR EACH ROW EXECUTE FUNCTION deny_evidence_mutation();
COMMIT;
