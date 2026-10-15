BEGIN;

-- ADR-195: one quoted, source-stated reviewed fact about an exact project.
-- The evidence array is frozen in the immutable row. This avoids an append-
-- after-review link that could silently widen the fact's source-grant set.
CREATE TABLE public.knowledge_project_facts (
    tenant_id uuid NOT NULL,
    id text NOT NULL CHECK (id ~ '^pfact_[a-f0-9]{32}$'),
    project_id text NOT NULL,
    predicate text NOT NULL CHECK (predicate ~ '^[a-z][a-z0-9_.-]{0,99}$'),
    value text NOT NULL CHECK (length(value) BETWEEN 1 AND 4000),
    value_type text NOT NULL CHECK (value_type IN ('text','number','date','boolean','reference')),
    assertion_status text NOT NULL CHECK (assertion_status IN ('asserted','disputed','retracted')),
    confidence double precision NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    derivation text NOT NULL DEFAULT 'source_stated'
        CHECK (derivation='source_stated'),
    evidence_ids text[] NOT NULL CHECK (cardinality(evidence_ids) BETWEEN 1 AND 20),
    quote_evidence_id text NOT NULL,
    source_quote text NOT NULL CHECK (length(source_quote) BETWEEN 1 AND 2000),
    observed_at timestamptz NOT NULL,
    valid_from timestamptz,
    valid_to timestamptz,
    supersedes_id text,
    reviewer_id uuid NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    FOREIGN KEY (tenant_id,project_id)
        REFERENCES public.knowledge_projects(tenant_id,id),
    FOREIGN KEY (tenant_id,quote_evidence_id)
        REFERENCES public.brain_evidence(tenant_id,id),
    FOREIGN KEY (tenant_id,supersedes_id)
        REFERENCES public.knowledge_project_facts(tenant_id,id),
    CHECK (valid_to IS NULL OR (valid_from IS NOT NULL AND valid_to>valid_from)),
    CHECK (quote_evidence_id=ANY(evidence_ids))
);
CREATE INDEX knowledge_project_facts_page
    ON public.knowledge_project_facts(tenant_id,project_id,recorded_at DESC,id DESC);
CREATE INDEX knowledge_project_facts_successor
    ON public.knowledge_project_facts(tenant_id,supersedes_id)
    WHERE supersedes_id IS NOT NULL;

-- The SQL boundary refuses arbitrary direct-runtime rows too; application
-- validation and a reviewer scope are additional, not substitute, controls.
CREATE FUNCTION public.guard_reviewed_project_fact() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
DECLARE prior record;
DECLARE evidence_count integer;
DECLARE valid_count integer;
BEGIN
    IF EXISTS (SELECT 1 FROM unnest(NEW.evidence_ids) AS item(id)
               WHERE item.id IS NULL OR item.id !~ '^evidence_[a-f0-9]{32}$')
       OR (SELECT count(DISTINCT item.id) FROM unnest(NEW.evidence_ids) AS item(id))
          <> cardinality(NEW.evidence_ids) THEN
        RAISE EXCEPTION 'invalid project fact evidence set';
    END IF;
    IF NEW.supersedes_id IS NOT NULL THEN
        SELECT f.project_id,f.predicate,f.value_type INTO prior
        FROM public.knowledge_project_facts AS f
        WHERE f.tenant_id=NEW.tenant_id AND f.id=NEW.supersedes_id;
        IF NOT FOUND OR prior.project_id<>NEW.project_id
           OR prior.predicate<>NEW.predicate OR prior.value_type<>NEW.value_type THEN
            RAISE EXCEPTION 'project fact supersession must keep project, predicate and type';
        END IF;
    END IF;
    evidence_count := cardinality(NEW.evidence_ids);
    SELECT count(*) INTO valid_count
    FROM public.brain_evidence AS e
    JOIN public.brain_source_versions AS v
      ON v.tenant_id=e.tenant_id AND v.id=e.source_version_id
    JOIN public.brain_source_items AS i
      ON i.tenant_id=v.tenant_id AND i.id=v.item_id AND i.source_id=v.source_id
    JOIN public.brain_sources AS s
      ON s.tenant_id=i.tenant_id AND s.id=i.source_id
    WHERE e.tenant_id=NEW.tenant_id AND e.id=ANY(NEW.evidence_ids)
      AND i.current_version_id=v.id AND s.status='active'
      AND NOT public.brain_email_evidence_is_excluded(e.tenant_id,e.id);
    IF valid_count<>evidence_count OR NOT EXISTS (
        SELECT 1 FROM public.brain_normalized_documents AS d
        WHERE d.tenant_id=NEW.tenant_id AND d.evidence_id=NEW.quote_evidence_id
          AND position(NEW.source_quote IN d.body)>0
    ) THEN
        RAISE EXCEPTION 'invalid project fact source basis';
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER reviewed_project_fact_guard
    BEFORE INSERT ON public.knowledge_project_facts
    FOR EACH ROW EXECUTE FUNCTION public.guard_reviewed_project_fact();

CREATE TABLE public.knowledge_project_fact_receipts (
    tenant_id uuid NOT NULL,
    actor_id uuid NOT NULL,
    idempotency_key uuid NOT NULL,
    request_sha256 text NOT NULL CHECK (request_sha256 ~ '^[a-f0-9]{64}$'),
    fact_id text NOT NULL,
    PRIMARY KEY (tenant_id,actor_id,idempotency_key),
    FOREIGN KEY (tenant_id,fact_id)
        REFERENCES public.knowledge_project_facts(tenant_id,id)
);

DO $block$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'knowledge_project_facts','knowledge_project_fact_receipts'
    ] LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',table_name);
        EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY',table_name);
        EXECUTE format('CREATE POLICY tenant_isolation ON public.%I USING
            (tenant_id=nullif(current_setting(''email_brain.tenant_id'',true),'''')::uuid)
            WITH CHECK (tenant_id=nullif(current_setting(''email_brain.tenant_id'',true),'''')::uuid)',table_name);
        EXECUTE format('CREATE POLICY tenant_login_fence ON public.%I AS RESTRICTIVE
            FOR ALL TO PUBLIC USING (public.masterbrain_tenant_login_allows(tenant_id))
            WITH CHECK (public.masterbrain_tenant_login_allows(tenant_id))',table_name);
        EXECUTE format('CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON public.%I
            FOR EACH ROW EXECUTE FUNCTION public.deny_evidence_mutation()',table_name);
        EXECUTE format('CREATE TRIGGER protected_no_truncate BEFORE TRUNCATE ON public.%I
            FOR EACH STATEMENT EXECUTE FUNCTION public.deny_protected_truncate()',table_name);
    END LOOP;
END $block$;

COMMIT;
