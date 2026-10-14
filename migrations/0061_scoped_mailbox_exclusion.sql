BEGIN;

-- Distinguish a provider deletion from a current-visibility exclusion.
-- Evidence and inventory rows remain immutable and tenant-fenced.
ALTER TABLE public.message_sync_state
    DROP CONSTRAINT message_sync_state_status_check;
ALTER TABLE public.message_sync_state
    ADD CONSTRAINT message_sync_state_status_check
    CHECK (status IN ('ready','quarantined','deleted','excluded'));

COMMIT;
