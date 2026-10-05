BEGIN;

-- ADR-161: read-side due-time lookup only; no commitment or evidence rewrite.
CREATE INDEX knowledge_commitments_due_lookup
    ON knowledge_commitments(tenant_id,due_at,id)
    WHERE due_at IS NOT NULL;
CREATE INDEX knowledge_commitments_project_due_lookup
    ON knowledge_commitments(tenant_id,project_id,due_at,id)
    WHERE due_at IS NOT NULL AND project_id IS NOT NULL;

COMMIT;
