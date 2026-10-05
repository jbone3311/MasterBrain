BEGIN;

-- ADR-160: read-side occurrence-time lookup only; no event or evidence rewrite.
CREATE INDEX knowledge_events_timeline_lookup
    ON knowledge_events(tenant_id,starts_at,id)
    WHERE starts_at IS NOT NULL;
CREATE INDEX knowledge_events_project_timeline_lookup
    ON knowledge_events(tenant_id,project_id,starts_at,id)
    WHERE starts_at IS NOT NULL AND project_id IS NOT NULL;

COMMIT;
