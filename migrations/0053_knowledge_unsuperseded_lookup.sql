BEGIN;

-- ADR-158: read-side review-chain lookup only. No assertion is rewritten.
CREATE INDEX knowledge_entities_supersedes_lookup
    ON knowledge_entities(tenant_id,supersedes_id)
    WHERE supersedes_id IS NOT NULL;
CREATE INDEX knowledge_relationships_supersedes_lookup
    ON knowledge_relationships(tenant_id,supersedes_id)
    WHERE supersedes_id IS NOT NULL;
CREATE INDEX knowledge_claims_supersedes_lookup
    ON knowledge_claims(tenant_id,supersedes_id)
    WHERE supersedes_id IS NOT NULL;
CREATE INDEX knowledge_events_supersedes_lookup
    ON knowledge_events(tenant_id,supersedes_id)
    WHERE supersedes_id IS NOT NULL;
CREATE INDEX knowledge_projects_supersedes_lookup
    ON knowledge_projects(tenant_id,supersedes_id)
    WHERE supersedes_id IS NOT NULL;
CREATE INDEX knowledge_commitments_supersedes_lookup
    ON knowledge_commitments(tenant_id,supersedes_id)
    WHERE supersedes_id IS NOT NULL;
CREATE INDEX knowledge_corrections_target_lookup
    ON knowledge_corrections(tenant_id,target_kind,target_id);

COMMIT;
