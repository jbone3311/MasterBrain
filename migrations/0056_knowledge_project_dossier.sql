BEGIN;

-- ADR-162: read-side linked-assertion order only; no evidence or heap rewrite.
CREATE INDEX knowledge_events_project_recorded_lookup
    ON knowledge_events(tenant_id,project_id,recorded_at DESC,id DESC)
    WHERE project_id IS NOT NULL;
CREATE INDEX knowledge_commitments_project_recorded_lookup
    ON knowledge_commitments(tenant_id,project_id,recorded_at DESC,id DESC)
    WHERE project_id IS NOT NULL;

COMMIT;
