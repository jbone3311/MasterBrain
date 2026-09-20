BEGIN;

-- Python datetime cannot decode PostgreSQL +/-infinity. Keep operator-visible
-- status rows portable without requiring a custom database codec.
ALTER TABLE sync_workers ALTER COLUMN lease_until SET DEFAULT '1970-01-01T00:00:00Z';
ALTER TABLE sync_workers ALTER COLUMN next_attempt_at SET DEFAULT '1970-01-01T00:00:00Z';
UPDATE sync_workers SET lease_until='1970-01-01T00:00:00Z' WHERE lease_until='-infinity';
UPDATE sync_workers SET next_attempt_at='1970-01-01T00:00:00Z' WHERE next_attempt_at='-infinity';

-- Snapshot the enrollment binding at lease acquisition. Existing abandoned leases
-- without this binding fail closed until reacquired.
ALTER TABLE sync_workers ADD COLUMN provider_account_id text
    CHECK (length(provider_account_id) BETWEEN 1 AND 512);

COMMIT;
