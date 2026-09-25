BEGIN;

CREATE INDEX brain_archive_member_image_current_search_idx
    ON brain_archive_member_image_receipts
    (tenant_id,document_id,inventory_id,member_locator,evidence_id);

COMMIT;
