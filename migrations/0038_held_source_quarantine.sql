-- Held messages whose source bytes exceed the retained storage budget.
--
-- A message the provider reports but whose raw size exceeds the configured store
-- limit is recorded as a quarantine receipt without retained bytes, so the worker can
-- advance past it instead of pausing the account. Existing receipts keep their bytes;
-- the new reason is the only one allowed to omit them. Catalog-only column change plus
-- constraint validation scans; no table rewrite.

BEGIN;

ALTER TABLE quarantine_receipts ALTER COLUMN raw_sha256 DROP NOT NULL;
ALTER TABLE quarantine_receipts DROP CONSTRAINT quarantine_receipts_reason_check;
ALTER TABLE quarantine_receipts ADD CONSTRAINT quarantine_receipts_reason_check
    CHECK (reason IN ('mime_rejected','mime_too_large','source_too_large'));
ALTER TABLE quarantine_receipts ADD CONSTRAINT quarantine_receipts_bytes_check
    CHECK ((raw_sha256 IS NULL) = (reason = 'source_too_large'));

COMMIT;
