BEGIN;

-- Immutable time/ID keyset order for all approval states, not only unfinished work.
CREATE INDEX recovery_jobs_history
    ON recovery_jobs(tenant_id,account_id,created_at DESC,id DESC);

COMMIT;
