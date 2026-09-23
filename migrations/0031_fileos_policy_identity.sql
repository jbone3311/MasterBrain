BEGIN;

-- Historical receipts did not retain their inventory policy. Keep that unknown
-- state instead of inventing a policy digest for immutable evidence.
ALTER TABLE brain_fileos_run_receipts ADD COLUMN policy_sha256 text;

-- NOT VALID preserves legacy NULL rows but enforces a real digest on every new
-- receipt. The immutable trigger prevents later edits to the historical rows.
ALTER TABLE brain_fileos_run_receipts ADD CONSTRAINT brain_fileos_policy_sha256_new
    CHECK (policy_sha256 IS NOT NULL AND policy_sha256 ~ '^[a-f0-9]{64}$') NOT VALID;

COMMIT;
