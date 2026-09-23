BEGIN;

-- Migration-role visibility is checked before any SQL file by migrate.py.
-- Freeze writes while checking old immutable rows; a discrepancy needs review,
-- never an inferred repair or a newly sealed false ledger.
LOCK TABLE brain_archive_inventories, brain_archive_members, brain_archive_skips
    IN SHARE ROW EXCLUSIVE MODE;
DO $block$
BEGIN
    IF EXISTS (
        SELECT 1 FROM brain_archive_inventories i
        CROSS JOIN LATERAL (
            SELECT count(*)::integer AS item_count,
                   COALESCE(sum(observed_size),0)::bigint AS observed_bytes
            FROM brain_archive_members m
            WHERE m.tenant_id=i.tenant_id AND m.inventory_id=i.id
        ) members
        CROSS JOIN LATERAL (
            SELECT count(*)::integer AS item_count
            FROM brain_archive_skips s
            WHERE s.tenant_id=i.tenant_id AND s.inventory_id=i.id
        ) skips
        WHERE members.item_count<>i.member_count
           OR skips.item_count<>i.skipped_count
           OR members.observed_bytes<>i.total_uncompressed_bytes
    ) THEN
        RAISE EXCEPTION 'existing archive inventory ledger requires review';
    END IF;
END $block$;

CREATE FUNCTION enforce_archive_child_ledger() RETURNS trigger
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
    IF NOT FOUND THEN
        RAISE EXCEPTION 'archive inventory parent unavailable';
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
END $function$;
CREATE CONSTRAINT TRIGGER archive_member_ledger
    AFTER INSERT ON brain_archive_members DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION enforce_archive_child_ledger();
CREATE CONSTRAINT TRIGGER archive_skip_ledger
    AFTER INSERT ON brain_archive_skips DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION enforce_archive_child_ledger();

ALTER TABLE brain_provenance
    ADD CONSTRAINT brain_provenance_output_document_fk
    FOREIGN KEY (tenant_id,output_id)
    REFERENCES brain_normalized_documents(tenant_id,id) NOT VALID;
ALTER TABLE brain_provenance
    VALIDATE CONSTRAINT brain_provenance_output_document_fk;

-- The parent inventory already references a source version. Reference its exact
-- composite identity, not an unrelated but otherwise valid source-version row.
ALTER TABLE brain_archive_inventories
    ADD CONSTRAINT brain_archive_inventory_parent_version_key
    UNIQUE (tenant_id,id,source_version_id);
ALTER TABLE brain_archive_member_text_receipts
    ADD CONSTRAINT brain_archive_text_parent_inventory_fk
    FOREIGN KEY (tenant_id,inventory_id,parent_source_version_id)
    REFERENCES brain_archive_inventories(tenant_id,id,source_version_id) NOT VALID;
ALTER TABLE brain_archive_member_document_receipts
    ADD CONSTRAINT brain_archive_document_parent_inventory_fk
    FOREIGN KEY (tenant_id,inventory_id,parent_source_version_id)
    REFERENCES brain_archive_inventories(tenant_id,id,source_version_id) NOT VALID;
ALTER TABLE brain_archive_member_image_receipts
    ADD CONSTRAINT brain_archive_image_parent_inventory_fk
    FOREIGN KEY (tenant_id,inventory_id,parent_source_version_id)
    REFERENCES brain_archive_inventories(tenant_id,id,source_version_id) NOT VALID;
ALTER TABLE brain_archive_member_text_receipts
    VALIDATE CONSTRAINT brain_archive_text_parent_inventory_fk;
ALTER TABLE brain_archive_member_document_receipts
    VALIDATE CONSTRAINT brain_archive_document_parent_inventory_fk;
ALTER TABLE brain_archive_member_image_receipts
    VALIDATE CONSTRAINT brain_archive_image_parent_inventory_fk;

COMMIT;
