-- Initial PostgreSQL tenant, account, cursor, event, and audit foundation.
-- The migration owner executes DDL. The application runtime role must not own
-- these tables and must not have BYPASSRLS.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE tenants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE tenant_memberships (
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id uuid NOT NULL,
    role text NOT NULL CHECK (role IN ('owner', 'member', 'reviewer', 'operator')),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, user_id)
);

CREATE TABLE mail_accounts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    provider text NOT NULL CHECK (provider IN ('fastmail', 'gmail', 'microsoft', 'icloud')),
    address text NOT NULL,
    secret_ref text NOT NULL,
    status text NOT NULL DEFAULT 'active',
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, provider, address)
);

CREATE TABLE sync_cursors (
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    account_id uuid NOT NULL REFERENCES mail_accounts(id) ON DELETE CASCADE,
    scope text NOT NULL,
    cursor_kind text NOT NULL,
    opaque_cursor text NOT NULL,
    generation bigint NOT NULL DEFAULT 1,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, account_id, scope)
);

CREATE TABLE provider_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    account_id uuid NOT NULL REFERENCES mail_accounts(id) ON DELETE CASCADE,
    event_key text NOT NULL,
    kind text NOT NULL,
    provider_object_id text NOT NULL,
    provider_version text,
    payload_ref text,
    observed_at timestamptz NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, account_id, event_key)
);

CREATE TABLE audit_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    actor_id uuid,
    request_id uuid NOT NULL,
    event_type text NOT NULL,
    resource_type text NOT NULL,
    resource_id text,
    outcome text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE tenant_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_memberships FORCE ROW LEVEL SECURITY;
ALTER TABLE mail_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE mail_accounts FORCE ROW LEVEL SECURITY;
ALTER TABLE sync_cursors ENABLE ROW LEVEL SECURITY;
ALTER TABLE sync_cursors FORCE ROW LEVEL SECURITY;
ALTER TABLE provider_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE provider_events FORCE ROW LEVEL SECURITY;
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_memberships_isolation ON tenant_memberships
    USING (tenant_id = current_setting('email_brain.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('email_brain.tenant_id', true)::uuid);
CREATE POLICY mail_accounts_isolation ON mail_accounts
    USING (tenant_id = current_setting('email_brain.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('email_brain.tenant_id', true)::uuid);
CREATE POLICY sync_cursors_isolation ON sync_cursors
    USING (tenant_id = current_setting('email_brain.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('email_brain.tenant_id', true)::uuid);
CREATE POLICY provider_events_isolation ON provider_events
    USING (tenant_id = current_setting('email_brain.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('email_brain.tenant_id', true)::uuid);
CREATE POLICY audit_events_isolation ON audit_events
    USING (tenant_id = current_setting('email_brain.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('email_brain.tenant_id', true)::uuid);

COMMIT;
