BEGIN;

-- Hold writers while the cross-tenant provenance check and missing-key repair
-- observe one stable set of current messages. Existing ledger rows stay intact.
LOCK TABLE messages, message_versions, message_sync_state
    IN SHARE ROW EXCLUSIVE MODE;

-- Repeat the exact mismatch predicate from 0008. On a deployment migrated by
-- a role subject to forced RLS, that earlier check may have seen no rows.
DO $block$
BEGIN
    IF EXISTS (
        SELECT 1 FROM messages m JOIN message_versions v
        ON v.tenant_id=m.tenant_id AND v.message_id=m.id AND v.raw_sha256=m.raw_sha256
        WHERE m.parser_version <> v.parser_version
    ) THEN
        RAISE EXCEPTION 'parser provenance mismatch; explicit evidence repair required';
    END IF;
END $block$;

INSERT INTO message_sync_state(tenant_id,account_id,provider_id,status)
    SELECT m.tenant_id,m.account_id,m.provider_message_id,
           CASE WHEN m.deleted THEN 'deleted'
                WHEN m.quarantined THEN 'quarantined'
                ELSE 'ready' END
    FROM messages m
    WHERE NOT EXISTS (
        SELECT 1 FROM message_sync_state s
        WHERE s.tenant_id=m.tenant_id AND s.account_id=m.account_id
          AND s.provider_id=m.provider_message_id
    )
    ON CONFLICT (tenant_id,account_id,provider_id) DO NOTHING;

DO $block$
BEGIN
    IF EXISTS (
        SELECT 1 FROM messages m
        WHERE NOT EXISTS (
            SELECT 1 FROM message_sync_state s
            WHERE s.tenant_id=m.tenant_id AND s.account_id=m.account_id
              AND s.provider_id=m.provider_message_id
        )
    ) THEN
        RAISE EXCEPTION 'message sync-state repair incomplete';
    END IF;
END $block$;

COMMIT;
