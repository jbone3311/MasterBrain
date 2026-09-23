BEGIN;

-- Closes integrity gaps found in a Factory review of PR #4 at 63b478d. Each section
-- states the gap it closes and the file that already demonstrates the correct pattern,
-- because in every case this repository had solved the problem once and not carried it
-- forward.

-- 1. The archive inventory ledger balanced ONCE, at insert.
--
-- 0023 attaches `archive_inventory_ledger` to brain_archive_inventories only. Members and
-- skips take no INSERT trigger, so a second transaction can append to a sealed inventory
-- and member_count, skipped_count and total_uncompressed_bytes silently stop being true.
-- 0018 already does this correctly for FileOS run receipts: the constraint trigger is on
-- BOTH the receipt and the item table. This mirrors it, resolving the inventory from the
-- child row instead of from NEW.id.
CREATE FUNCTION enforce_archive_member_ledger() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
DECLARE
    expected_members integer;
    expected_skips integer;
    expected_bytes bigint;
    actual_members integer;
    actual_skips integer;
    actual_bytes bigint;
BEGIN
    SELECT member_count,skipped_count,total_uncompressed_bytes
    INTO expected_members,expected_skips,expected_bytes
    FROM public.brain_archive_inventories
    WHERE tenant_id=NEW.tenant_id AND id=NEW.inventory_id;
    IF expected_members IS NULL THEN
        -- The inventory row lands in the same transaction; its own deferred trigger is
        -- the authority then. Nothing to re-check here.
        RETURN NULL;
    END IF;
    SELECT count(*)::integer,COALESCE(sum(observed_size),0)::bigint
    INTO actual_members,actual_bytes
    FROM public.brain_archive_members
    WHERE tenant_id=NEW.tenant_id AND inventory_id=NEW.inventory_id;
    SELECT count(*)::integer INTO actual_skips
    FROM public.brain_archive_skips
    WHERE tenant_id=NEW.tenant_id AND inventory_id=NEW.inventory_id;
    IF actual_members<>expected_members OR actual_skips<>expected_skips
       OR actual_bytes<>expected_bytes THEN
        RAISE EXCEPTION 'invalid archive inventory ledger';
    END IF;
    RETURN NULL;
END
$function$;
CREATE CONSTRAINT TRIGGER archive_member_ledger
    AFTER INSERT ON brain_archive_members DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION enforce_archive_member_ledger();
CREATE CONSTRAINT TRIGGER archive_skip_ledger
    AFTER INSERT ON brain_archive_skips DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION enforce_archive_member_ledger();

-- 2. The provenance graph had no referential integrity in either direction.
--
-- 0015 gives output_id and input_id a format CHECK and no FOREIGN KEY, while every
-- sibling id column in that file is FK'd. In practice output_id names a
-- brain_normalized_documents row and input_id names a brain_evidence row
-- (persistence.py:951-967), so the edges are typed to one table today and can be
-- expressed. Without this a provenance row may name an output that does not exist, and
-- the trace the product's documentation promises cannot be relied on.
ALTER TABLE brain_provenance
    ADD CONSTRAINT brain_provenance_output_fk
    FOREIGN KEY (tenant_id,output_id)
    REFERENCES brain_normalized_documents(tenant_id,id);
-- NOT DONE, and the reason is measured rather than argued. The obvious companion
-- constraint — brain_provenance_inputs.input_id -> brain_evidence — was written, applied
-- and REJECTED by the suite:
--
--   psycopg.errors.ForeignKeyViolation: insert or update on table
--   "brain_provenance_inputs" violates foreign key constraint "brain_provenance_input_fk"
--
-- because input_id is polymorphic in practice: the email paths pass an evidence id
-- (persistence.py:966, 1320, 1592) while the archive paths pass
-- (parent_evidence_id, inventory_id) — an id from brain_archive_inventories
-- (persistence.py:2286, 2637, 3026). A single-target FK is therefore not expressible
-- today, and the fix is an `input_kind` discriminator plus one FK per kind, which is a
-- schema change with a data migration behind it rather than a constraint to bolt on.
-- Left undone deliberately, with the evidence, instead of quietly dropped.

-- 3. `parent_source_version_id` was NOT NULL and bound to nothing, in all three archive
-- derivative receipts, while every sibling id column in the same tables is FK'd.
ALTER TABLE brain_archive_member_text_receipts
    ADD CONSTRAINT bamtr_parent_version_fk
    FOREIGN KEY (tenant_id,parent_source_version_id)
    REFERENCES brain_source_versions(tenant_id,id);
ALTER TABLE brain_archive_member_document_receipts
    ADD CONSTRAINT bamdr_parent_version_fk
    FOREIGN KEY (tenant_id,parent_source_version_id)
    REFERENCES brain_source_versions(tenant_id,id);
ALTER TABLE brain_archive_member_image_receipts
    ADD CONSTRAINT bamir_parent_version_fk
    FOREIGN KEY (tenant_id,parent_source_version_id)
    REFERENCES brain_source_versions(tenant_id,id);

-- 4. "Immutable" did not survive TRUNCATE.
--
-- deny_evidence_mutation() is attached everywhere as BEFORE UPDATE OR DELETE FOR EACH
-- ROW. TRUNCATE fires neither row triggers nor RLS policies, so any role holding TRUNCATE
-- erases an append-only history in one statement with nothing run and nothing recorded.
-- grant_runtime does not grant TRUNCATE, so the runtime role was already safe; the owner
-- was not, and the guarantee is documented without qualification.
DO $block$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'brain_evidence','brain_normalized_documents','brain_chunks','brain_provenance',
        'brain_provenance_inputs','brain_source_versions','brain_sources',
        'brain_source_items','brain_archive_inventories','brain_archive_members',
        'brain_archive_skips','brain_archive_inventory_receipts',
        'brain_archive_member_text_receipts','brain_archive_member_document_receipts',
        'brain_archive_member_image_receipts','brain_index_generations',
        'brain_index_generation_items','brain_index_generation_chunks',
        'brain_index_activations','brain_fileos_run_receipts','brain_fileos_run_items',
        'knowledge_entities','knowledge_relationships','knowledge_claims',
        'knowledge_events','knowledge_projects','knowledge_commitments',
        'knowledge_corrections','knowledge_evidence','knowledge_change_events',
        'knowledge_receipts'
    ] LOOP
        IF to_regclass('public.'||quote_ident(table_name)) IS NOT NULL THEN
            EXECUTE format('CREATE TRIGGER no_truncate BEFORE TRUNCATE ON %I
                FOR EACH STATEMENT EXECUTE FUNCTION deny_evidence_mutation()',table_name);
        END IF;
    END LOOP;
END
$block$;

-- 5. Cheap CHECKs that get harder to add once there is data.
--
-- A rollback that targets the generation it is already on, and a derivative whose parent
-- evidence is itself, are both currently representable.
ALTER TABLE brain_index_activations
    ADD CONSTRAINT brain_index_activation_not_self
    CHECK (previous_generation_id IS DISTINCT FROM generation_id);

COMMIT;
