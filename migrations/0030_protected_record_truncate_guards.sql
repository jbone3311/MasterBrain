BEGIN;

-- TRUNCATE bypasses row triggers and RLS. This function is deliberately not
-- SECURITY DEFINER and confers no privilege on a runtime role.
CREATE FUNCTION deny_protected_truncate() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
    RAISE EXCEPTION 'protected record; retention requires a separately authorized maintenance path';
END $body$;
REVOKE ALL ON FUNCTION deny_protected_truncate() FROM PUBLIC;

DO $block$
DECLARE
    table_name text;
    baseline_names text[] := ARRAY[
        'audit_events','raw_objects','provider_events','message_versions',
        'intake_events','sync_runs','sync_inventory','quarantine_receipts',
        'sync_inventory_seals','rule_simulations','rule_revisions',
        'recovery_attempts','attachment_receipts','document_extractions',
        'memory_records','memory_revisions','memory_receipts',
        'brain_source_versions','brain_evidence','brain_normalized_documents',
        'brain_chunks','brain_provenance','brain_provenance_inputs',
        'brain_change_events','brain_import_receipts',
        'knowledge_entities','knowledge_entity_aliases','knowledge_relationships',
        'knowledge_claims','knowledge_projects','knowledge_events',
        'knowledge_commitments','knowledge_corrections','knowledge_evidence',
        'knowledge_search_documents','knowledge_change_events','knowledge_receipts',
        'brain_fileos_run_receipts','brain_fileos_run_items',
        'brain_fileos_absence_events','brain_index_generations',
        'brain_index_generation_items','brain_index_generation_chunks',
        'brain_index_generation_receipts','brain_index_activations',
        'brain_email_bridge_receipts','brain_parts',
        'brain_email_attachment_bridge_receipts',
        'brain_email_document_bridge_receipts','brain_archive_inventories',
        'brain_archive_members','brain_archive_skips',
        'brain_archive_inventory_receipts',
        'brain_archive_member_text_receipts',
        'brain_archive_member_document_receipts',
        'brain_archive_member_image_receipts'
    ];
BEGIN
    IF cardinality(baseline_names) <> 56 THEN
        RAISE EXCEPTION 'protected-record baseline inventory changed';
    END IF;

    -- Refuse a schema where any accepted append-only row guard is absent or
    -- disabled. Newer direct guards are included by the catalog loop below.
    FOREACH table_name IN ARRAY baseline_names LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_trigger t
            JOIN pg_class c ON c.oid=t.tgrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' AND c.relname=table_name
              AND NOT t.tgisinternal AND t.tgenabled IN ('O','A')
              AND t.tgfoid='public.deny_evidence_mutation()'::regprocedure
              AND (t.tgtype & 1)=1 AND (t.tgtype & 2)=2
              AND (t.tgtype & 8)=8 AND (t.tgtype & 16)=16
        ) THEN
            RAISE EXCEPTION 'missing enabled row guard for protected table %', table_name;
        END IF;
    END LOOP;

    FOR table_name IN
        SELECT DISTINCT c.relname
        FROM pg_trigger t
        JOIN pg_class c ON c.oid=t.tgrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND NOT t.tgisinternal
          AND t.tgenabled IN ('O','A')
          AND t.tgfoid='public.deny_evidence_mutation()'::regprocedure
          AND (t.tgtype & 1)=1 AND (t.tgtype & 2)=2
          AND (t.tgtype & 8)=8 AND (t.tgtype & 16)=16
        ORDER BY c.relname
    LOOP
        EXECUTE format('CREATE TRIGGER protected_no_truncate BEFORE TRUNCATE ON public.%I
            FOR EACH STATEMENT EXECUTE FUNCTION public.deny_protected_truncate()',table_name);
    END LOOP;

    -- Stateful approval jobs forbid DELETE; identity deletion is audited. All
    -- three otherwise admit an unguarded, unaudited whole-table TRUNCATE.
    FOREACH table_name IN ARRAY ARRAY[
        'recovery_jobs','document_jobs','external_identities'
    ] LOOP
        EXECUTE format('CREATE TRIGGER protected_no_truncate BEFORE TRUNCATE ON public.%I
            FOR EACH STATEMENT EXECUTE FUNCTION public.deny_protected_truncate()',table_name);
    END LOOP;
END $block$;

COMMIT;
