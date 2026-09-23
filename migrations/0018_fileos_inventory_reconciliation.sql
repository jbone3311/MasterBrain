BEGIN;
ALTER TABLE brain_fileos_run_receipts ADD CONSTRAINT brain_fileos_receipt_source_time
    UNIQUE (tenant_id,actor_id,run_id,source_id,observed_at);
CREATE TABLE brain_fileos_run_items (
    tenant_id uuid NOT NULL,
    actor_id uuid NOT NULL,
    run_id uuid NOT NULL,
    source_id text NOT NULL,
    observed_at timestamptz NOT NULL,
    item_id text NOT NULL,
    version_id text NOT NULL,
    outcome text NOT NULL CHECK (
        outcome IN ('extracted','empty','unsupported','deferred','changed','failed')
    ),
    PRIMARY KEY (tenant_id,actor_id,run_id,item_id),
    UNIQUE (tenant_id,actor_id,run_id,source_id,item_id),
    FOREIGN KEY (tenant_id,actor_id,run_id,source_id,observed_at)
        REFERENCES brain_fileos_run_receipts(
            tenant_id,actor_id,run_id,source_id,observed_at
        ),
    FOREIGN KEY (tenant_id,source_id,item_id,version_id)
        REFERENCES brain_source_versions(tenant_id,source_id,item_id,id)
);
CREATE INDEX brain_fileos_run_items_source
    ON brain_fileos_run_items(tenant_id,source_id,run_id,item_id);

CREATE TABLE brain_fileos_absence_events (
    tenant_id uuid NOT NULL,
    id text NOT NULL CHECK (id ~ '^[a-z][a-z0-9_-]{0,127}$'),
    source_id text NOT NULL,
    item_id text NOT NULL,
    version_id text NOT NULL,
    previous_actor_id uuid NOT NULL,
    previous_run_id uuid NOT NULL,
    observed_actor_id uuid NOT NULL,
    observed_run_id uuid NOT NULL,
    observed_at timestamptz NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    FOREIGN KEY (tenant_id,source_id,item_id,version_id)
        REFERENCES brain_source_versions(tenant_id,source_id,item_id,id),
    FOREIGN KEY (tenant_id,previous_actor_id,previous_run_id,source_id,item_id)
        REFERENCES brain_fileos_run_items(tenant_id,actor_id,run_id,source_id,item_id),
    FOREIGN KEY (
        tenant_id,observed_actor_id,observed_run_id,source_id,observed_at
    ) REFERENCES brain_fileos_run_receipts(
        tenant_id,actor_id,run_id,source_id,observed_at
    )
);
CREATE INDEX brain_fileos_absence_by_run
    ON brain_fileos_absence_events(tenant_id,source_id,observed_run_id,id);

CREATE FUNCTION enforce_fileos_run_item_ledger() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
DECLARE
    expected_count integer;
    expected_outcomes jsonb;
    actual_count integer;
    actual_outcomes jsonb;
BEGIN
    SELECT item_count,outcomes INTO expected_count,expected_outcomes
    FROM public.brain_fileos_run_receipts
    WHERE tenant_id=NEW.tenant_id AND actor_id=NEW.actor_id AND run_id=NEW.run_id;
    SELECT COALESCE(sum(n),0)::integer,COALESCE(jsonb_object_agg(outcome,n),'{}'::jsonb)
    INTO actual_count,actual_outcomes
    FROM (
        SELECT outcome,count(*)::integer AS n
        FROM public.brain_fileos_run_items
        WHERE tenant_id=NEW.tenant_id AND actor_id=NEW.actor_id AND run_id=NEW.run_id
        GROUP BY outcome
    ) grouped;
    IF expected_count IS NULL OR actual_count<>expected_count
       OR actual_outcomes<>expected_outcomes THEN
        RAISE EXCEPTION 'invalid FileOS run item ledger';
    END IF;
    RETURN NULL;
END
$function$;
CREATE CONSTRAINT TRIGGER fileos_receipt_item_ledger
    AFTER INSERT ON brain_fileos_run_receipts DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION enforce_fileos_run_item_ledger();
CREATE CONSTRAINT TRIGGER fileos_run_item_ledger
    AFTER INSERT ON brain_fileos_run_items DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION enforce_fileos_run_item_ledger();

DO $block$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'brain_fileos_run_items','brain_fileos_absence_events'
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
