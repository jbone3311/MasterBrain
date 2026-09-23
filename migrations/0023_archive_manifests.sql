BEGIN;
CREATE TABLE brain_archive_inventories (
    tenant_id uuid NOT NULL,
    id text NOT NULL CHECK (id ~ '^[a-z][a-z0-9_-]{0,127}$'),
    source_id text NOT NULL,
    item_id text NOT NULL,
    source_version_id text NOT NULL,
    processor_version text NOT NULL CHECK (
        processor_version ~ '^sandbox-fileos-archive-v1-[a-f0-9]{64}$'
    ),
    result_sha256 text NOT NULL CHECK (result_sha256 ~ '^[a-f0-9]{64}$'),
    archive_format text NOT NULL CHECK (archive_format IN ('zip','tar')),
    status text NOT NULL CHECK (status IN ('complete','partial')),
    reason text NOT NULL CHECK (
        (status='complete' AND reason='bounded_archive_v1') OR
        (status='partial' AND reason='bounded_archive_partial_v1')
    ),
    member_count integer NOT NULL CHECK (member_count BETWEEN 0 AND 2000),
    skipped_count integer NOT NULL CHECK (skipped_count BETWEEN 0 AND 2001),
    file_count integer NOT NULL CHECK (file_count=member_count),
    total_uncompressed_bytes bigint NOT NULL CHECK (
        total_uncompressed_bytes BETWEEN 0 AND 268435456
    ),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    UNIQUE (tenant_id,source_version_id,processor_version),
    FOREIGN KEY (tenant_id,source_id,item_id,source_version_id)
        REFERENCES brain_source_versions(tenant_id,source_id,item_id,id)
);

CREATE TABLE brain_archive_members (
    tenant_id uuid NOT NULL,
    inventory_id text NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal BETWEEN 0 AND 1999),
    locator text NOT NULL CHECK (length(locator) BETWEEN 1 AND 1024),
    sha256 text NOT NULL CHECK (sha256 ~ '^[a-f0-9]{64}$'),
    declared_size bigint NOT NULL CHECK (declared_size BETWEEN 0 AND 67108864),
    observed_size bigint NOT NULL CHECK (observed_size=declared_size),
    media_hint text NOT NULL CHECK (length(media_hint) BETWEEN 1 AND 100),
    depth integer NOT NULL CHECK (depth BETWEEN 0 AND 3),
    parent_locator text,
    is_container boolean NOT NULL,
    PRIMARY KEY (tenant_id,inventory_id,ordinal),
    UNIQUE (tenant_id,inventory_id,locator),
    FOREIGN KEY (tenant_id,inventory_id)
        REFERENCES brain_archive_inventories(tenant_id,id),
    FOREIGN KEY (tenant_id,inventory_id,parent_locator)
        REFERENCES brain_archive_members(tenant_id,inventory_id,locator)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE brain_archive_skips (
    tenant_id uuid NOT NULL,
    inventory_id text NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal BETWEEN 0 AND 2000),
    locator text NOT NULL CHECK (length(locator) BETWEEN 1 AND 1024),
    reason text NOT NULL CHECK (
        reason IN ('dotfile','traversal','encrypted','link','non_regular',
                   'depth_limit','unreadable','bomb_limit')
    ),
    depth integer NOT NULL CHECK (depth BETWEEN 0 AND 3),
    parent_locator text,
    PRIMARY KEY (tenant_id,inventory_id,ordinal),
    FOREIGN KEY (tenant_id,inventory_id)
        REFERENCES brain_archive_inventories(tenant_id,id),
    FOREIGN KEY (tenant_id,inventory_id,parent_locator)
        REFERENCES brain_archive_members(tenant_id,inventory_id,locator)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE brain_archive_inventory_receipts (
    tenant_id uuid NOT NULL,
    actor_id uuid NOT NULL,
    idempotency_key uuid NOT NULL,
    request_hash text NOT NULL CHECK (request_hash ~ '^[a-f0-9]{64}$'),
    inventory_id text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,actor_id,idempotency_key),
    FOREIGN KEY (tenant_id,inventory_id)
        REFERENCES brain_archive_inventories(tenant_id,id)
);

CREATE FUNCTION enforce_archive_inventory_ledger() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
DECLARE
    actual_members integer;
    actual_skips integer;
    actual_bytes bigint;
BEGIN
    SELECT count(*)::integer,COALESCE(sum(observed_size),0)::bigint
    INTO actual_members,actual_bytes
    FROM public.brain_archive_members
    WHERE tenant_id=NEW.tenant_id AND inventory_id=NEW.id;
    SELECT count(*)::integer INTO actual_skips
    FROM public.brain_archive_skips
    WHERE tenant_id=NEW.tenant_id AND inventory_id=NEW.id;
    IF actual_members<>NEW.member_count OR actual_skips<>NEW.skipped_count
       OR actual_bytes<>NEW.total_uncompressed_bytes THEN
        RAISE EXCEPTION 'invalid archive inventory ledger';
    END IF;
    RETURN NULL;
END
$function$;
CREATE CONSTRAINT TRIGGER archive_inventory_ledger
    AFTER INSERT ON brain_archive_inventories DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION enforce_archive_inventory_ledger();

DO $block$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'brain_archive_inventories','brain_archive_members','brain_archive_skips',
        'brain_archive_inventory_receipts'
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
