BEGIN;
CREATE TABLE rule_simulations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    actor_id uuid NOT NULL,
    proposal_id uuid NOT NULL,
    proposal_version integer NOT NULL CHECK (proposal_version > 0),
    proposal_hash text NOT NULL,
    base_revision bigint NOT NULL CHECK (base_revision >= 0),
    sample jsonb NOT NULL CHECK (jsonb_typeof(sample)='array' AND jsonb_array_length(sample)<=50),
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL DEFAULT now()+interval '15 minutes',
    CHECK (isfinite(expires_at) AND expires_at>created_at),
    UNIQUE (tenant_id,id),
    FOREIGN KEY (tenant_id,proposal_id) REFERENCES proposals(tenant_id,id)
);
CREATE TABLE rule_revisions (
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    revision bigint NOT NULL CHECK (revision > 0),
    actor_id uuid NOT NULL,
    rules jsonb NOT NULL CHECK (jsonb_typeof(rules)='array' AND jsonb_array_length(rules)<=100),
    simulation_id uuid,
    restored_from bigint CHECK (restored_from>=0 AND restored_from<revision),
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK ((simulation_id IS NULL) <> (restored_from IS NULL)),
    PRIMARY KEY (tenant_id,revision),
    UNIQUE (tenant_id,simulation_id),
    FOREIGN KEY (tenant_id,simulation_id) REFERENCES rule_simulations(tenant_id,id)
);
DO $block$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY['rule_simulations','rule_revisions'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', table_name);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', table_name);
        EXECUTE format('CREATE POLICY tenant_isolation ON %I USING
            (tenant_id=nullif(current_setting(''email_brain.tenant_id'',true),'''')::uuid)
            WITH CHECK (tenant_id=nullif(current_setting(''email_brain.tenant_id'',true),'''')::uuid)',
            table_name);
        EXECUTE format('CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON %I
            FOR EACH ROW EXECUTE FUNCTION deny_evidence_mutation()', table_name);
    END LOOP;
END $block$;
COMMIT;
