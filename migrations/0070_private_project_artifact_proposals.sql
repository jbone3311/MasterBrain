BEGIN;

-- ADR-207: artifact links have their own publication receipt. These rows are
-- private and inert until an explicit human decision publishes a reviewed link.
CREATE TABLE public.knowledge_artifact_proposal_batches (
    tenant_id uuid NOT NULL,
    id text NOT NULL CHECK (id ~ '^kabatch_[a-f0-9]{32}$'),
    proposer_id uuid NOT NULL,
    idempotency_key uuid NOT NULL,
    request_sha256 text NOT NULL CHECK (request_sha256 ~ '^[a-f0-9]{64}$'),
    import_context_sha256 text NOT NULL CHECK (import_context_sha256 ~ '^[a-f0-9]{64}$'),
    row_count integer NOT NULL CHECK (row_count BETWEEN 1 AND 50),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    UNIQUE (tenant_id,proposer_id,idempotency_key)
);

CREATE TABLE public.knowledge_artifact_proposals (
    tenant_id uuid NOT NULL,
    id text NOT NULL CHECK (id ~ '^kaproposal_[a-f0-9]{32}$'),
    batch_id text NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal BETWEEN 0 AND 49),
    claimed_id text NOT NULL CHECK (claimed_id ~ '^partifact_[a-f0-9]{32}$'),
    project_id text NOT NULL,
    payload jsonb NOT NULL CHECK (
        jsonb_typeof(payload)='object' AND octet_length(payload::text)<=8000
        AND NOT (payload ? 'reviewed')
    ),
    payload_sha256 text NOT NULL CHECK (payload_sha256 ~ '^[a-f0-9]{64}$'),
    artifact_evidence_id text NOT NULL CHECK (artifact_evidence_id ~ '^evidence_[a-f0-9]{32}$'),
    basis_evidence_id text NOT NULL CHECK (basis_evidence_id ~ '^evidence_[a-f0-9]{32}$'),
    artifact_source_kind text NOT NULL CHECK (artifact_source_kind IN ('email','fileos')),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    UNIQUE (tenant_id,batch_id,ordinal),
    UNIQUE (tenant_id,batch_id,id),
    UNIQUE (tenant_id,batch_id,claimed_id),
    FOREIGN KEY (tenant_id,batch_id)
        REFERENCES public.knowledge_artifact_proposal_batches(tenant_id,id),
    FOREIGN KEY (tenant_id,project_id)
        REFERENCES public.knowledge_projects(tenant_id,id),
    FOREIGN KEY (tenant_id,artifact_evidence_id)
        REFERENCES public.brain_evidence(tenant_id,id),
    FOREIGN KEY (tenant_id,basis_evidence_id)
        REFERENCES public.brain_evidence(tenant_id,id)
);

CREATE TABLE public.knowledge_artifact_proposal_decisions (
    tenant_id uuid NOT NULL,
    batch_id text NOT NULL,
    proposal_id text NOT NULL,
    decision text NOT NULL CHECK (decision IN ('approved','rejected')),
    reviewer_id uuid NOT NULL,
    reason text,
    publication_key uuid,
    link_id text,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,proposal_id),
    FOREIGN KEY (tenant_id,batch_id,proposal_id)
        REFERENCES public.knowledge_artifact_proposals(tenant_id,batch_id,id),
    FOREIGN KEY (tenant_id,reviewer_id,publication_key)
        REFERENCES public.knowledge_project_artifact_receipts(tenant_id,actor_id,idempotency_key),
    FOREIGN KEY (tenant_id,link_id)
        REFERENCES public.knowledge_project_artifacts(tenant_id,id),
    CHECK (
        (decision='approved' AND reason IS NULL AND publication_key IS NOT NULL
         AND link_id IS NOT NULL)
        OR
        (decision='rejected' AND reason IS NOT NULL AND length(reason) BETWEEN 1 AND 500
         AND publication_key IS NULL AND link_id IS NULL)
    )
);

CREATE TABLE public.knowledge_artifact_proposal_review_receipts (
    tenant_id uuid NOT NULL,
    reviewer_id uuid NOT NULL,
    idempotency_key uuid NOT NULL,
    batch_id text NOT NULL,
    request_sha256 text NOT NULL CHECK (request_sha256 ~ '^[a-f0-9]{64}$'),
    approved_count integer NOT NULL CHECK (approved_count BETWEEN 0 AND 50),
    rejected_count integer NOT NULL CHECK (rejected_count BETWEEN 0 AND 50),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,reviewer_id,idempotency_key),
    UNIQUE (tenant_id,batch_id),
    FOREIGN KEY (tenant_id,batch_id)
        REFERENCES public.knowledge_artifact_proposal_batches(tenant_id,id),
    CHECK (approved_count+rejected_count BETWEEN 1 AND 50)
);

CREATE FUNCTION public.guard_artifact_proposal_basis() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
BEGIN
    IF NEW.artifact_evidence_id IS DISTINCT FROM NEW.payload->>'artifact_evidence_id'
       OR NEW.basis_evidence_id IS DISTINCT FROM NEW.payload->>'basis_evidence_id'
       OR NOT EXISTS (
           SELECT 1 FROM public.brain_evidence e
           JOIN public.brain_source_versions v
             ON v.tenant_id=e.tenant_id AND v.id=e.source_version_id
           JOIN public.brain_sources s
             ON s.tenant_id=v.tenant_id AND s.id=v.source_id
           WHERE e.tenant_id=NEW.tenant_id AND e.id=NEW.artifact_evidence_id
             AND s.kind=NEW.artifact_source_kind
       ) THEN
        RAISE EXCEPTION 'invalid artifact proposal citation or kind';
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER artifact_proposal_basis
    BEFORE INSERT ON public.knowledge_artifact_proposals
    FOR EACH ROW EXECUTE FUNCTION public.guard_artifact_proposal_basis();

CREATE FUNCTION public.require_artifact_proposal_batch_complete() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
BEGIN
    IF (SELECT count(*) FROM public.knowledge_artifact_proposals p
        WHERE p.tenant_id=NEW.tenant_id AND p.batch_id=NEW.id) <> NEW.row_count THEN
        RAISE EXCEPTION 'incomplete artifact proposal batch';
    END IF;
    RETURN NULL;
END
$function$;
CREATE CONSTRAINT TRIGGER artifact_proposal_batch_complete
    AFTER INSERT ON public.knowledge_artifact_proposal_batches
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION public.require_artifact_proposal_batch_complete();

CREATE FUNCTION public.guard_artifact_proposal_decision() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
BEGIN
    IF NEW.decision='approved' AND NOT EXISTS (
        SELECT 1 FROM public.knowledge_project_artifact_receipts r
        JOIN public.knowledge_project_artifacts l
          ON l.tenant_id=r.tenant_id AND l.id=r.link_id
        JOIN public.knowledge_artifact_proposals p
          ON p.tenant_id=NEW.tenant_id AND p.id=NEW.proposal_id
        WHERE r.tenant_id=NEW.tenant_id AND r.actor_id=NEW.reviewer_id
          AND r.idempotency_key=NEW.publication_key AND r.link_id=NEW.link_id
          AND p.batch_id=NEW.batch_id
          AND l.project_id=p.project_id
          AND l.artifact_evidence_id=p.artifact_evidence_id
          AND l.basis_evidence_id=p.basis_evidence_id
          AND l.relation=p.payload->>'relation'
          AND l.assertion_status=p.payload->>'assertion_status'
          AND l.source_quote=p.payload->>'source_quote'
          AND l.observed_at=(p.payload->>'observed_at')::timestamptz
    ) THEN
        RAISE EXCEPTION 'invalid artifact proposal approval receipt';
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER artifact_proposal_decision_basis
    BEFORE INSERT ON public.knowledge_artifact_proposal_decisions
    FOR EACH ROW EXECUTE FUNCTION public.guard_artifact_proposal_decision();

CREATE FUNCTION public.require_artifact_proposal_review_complete() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
DECLARE expected_count integer;
DECLARE actual_approved integer;
DECLARE actual_rejected integer;
BEGIN
    SELECT b.row_count INTO expected_count
    FROM public.knowledge_artifact_proposal_batches b
    WHERE b.tenant_id=NEW.tenant_id AND b.id=NEW.batch_id;
    SELECT count(*) FILTER (WHERE d.decision='approved'),
           count(*) FILTER (WHERE d.decision='rejected')
      INTO actual_approved,actual_rejected
    FROM public.knowledge_artifact_proposal_decisions d
    WHERE d.tenant_id=NEW.tenant_id AND d.batch_id=NEW.batch_id
      AND d.reviewer_id=NEW.reviewer_id;
    IF expected_count IS NULL OR actual_approved<>NEW.approved_count
       OR actual_rejected<>NEW.rejected_count
       OR actual_approved+actual_rejected<>expected_count THEN
        RAISE EXCEPTION 'incomplete artifact proposal review';
    END IF;
    RETURN NULL;
END
$function$;
CREATE CONSTRAINT TRIGGER artifact_proposal_review_complete
    AFTER INSERT ON public.knowledge_artifact_proposal_review_receipts
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION public.require_artifact_proposal_review_complete();

CREATE FUNCTION public.require_artifact_proposal_decision_review() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM public.knowledge_artifact_proposal_review_receipts r
        WHERE r.tenant_id=NEW.tenant_id AND r.batch_id=NEW.batch_id
          AND r.reviewer_id=NEW.reviewer_id
    ) THEN
        RAISE EXCEPTION 'artifact proposal decision lacks review receipt';
    END IF;
    RETURN NULL;
END
$function$;
CREATE CONSTRAINT TRIGGER artifact_proposal_decision_review
    AFTER INSERT ON public.knowledge_artifact_proposal_decisions
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION public.require_artifact_proposal_decision_review();

DO $block$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'knowledge_artifact_proposal_batches','knowledge_artifact_proposals',
        'knowledge_artifact_proposal_decisions',
        'knowledge_artifact_proposal_review_receipts'
    ] LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',table_name);
        EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY',table_name);
        EXECUTE format('CREATE POLICY tenant_isolation ON public.%I USING '
            || '(tenant_id=nullif(current_setting(''email_brain.tenant_id'',true),'''')::uuid) '
            || 'WITH CHECK (tenant_id=nullif(current_setting(''email_brain.tenant_id'',true),'''')::uuid)',
            table_name);
        EXECUTE format('CREATE POLICY tenant_login_fence ON public.%I AS RESTRICTIVE '
            || 'FOR ALL TO PUBLIC USING (public.masterbrain_tenant_login_allows(tenant_id)) '
            || 'WITH CHECK (public.masterbrain_tenant_login_allows(tenant_id))',table_name);
        EXECUTE format('CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON public.%I '
            || 'FOR EACH ROW EXECUTE FUNCTION public.deny_evidence_mutation()',table_name);
        EXECUTE format('CREATE TRIGGER protected_no_truncate BEFORE TRUNCATE ON public.%I '
            || 'FOR EACH STATEMENT EXECUTE FUNCTION public.deny_protected_truncate()',table_name);
    END LOOP;
END $block$;

COMMIT;
