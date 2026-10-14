BEGIN;

-- ADR-186: proposals are separate from reviewed assertions and search.
CREATE TABLE public.knowledge_proposal_batches (
    tenant_id uuid NOT NULL,
    id text NOT NULL CHECK (id ~ '^kbatch_[a-f0-9]{32}$'),
    proposer_id uuid NOT NULL,
    idempotency_key uuid NOT NULL,
    request_sha256 text NOT NULL CHECK (request_sha256 ~ '^[a-f0-9]{64}$'),
    row_count integer NOT NULL CHECK (row_count BETWEEN 1 AND 50),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    UNIQUE (tenant_id,proposer_id,idempotency_key)
);

CREATE TABLE public.knowledge_proposals (
    tenant_id uuid NOT NULL,
    id text NOT NULL CHECK (id ~ '^kproposal_[a-f0-9]{32}$'),
    batch_id text NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal BETWEEN 0 AND 49),
    payload jsonb NOT NULL CHECK (
        jsonb_typeof(payload)='object' AND octet_length(payload::text)<=12000
        AND payload ? 'kind' AND payload ? 'evidence_ids'
        AND jsonb_typeof(payload->'evidence_ids')='array'
        AND NOT (payload ? 'reviewed')
    ),
    payload_sha256 text NOT NULL CHECK (payload_sha256 ~ '^[a-f0-9]{64}$'),
    evidence_count integer NOT NULL CHECK (evidence_count BETWEEN 1 AND 20),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    UNIQUE (tenant_id,batch_id,ordinal),
    UNIQUE (tenant_id,batch_id,id),
    FOREIGN KEY (tenant_id,batch_id)
        REFERENCES public.knowledge_proposal_batches(tenant_id,id)
);
CREATE INDEX knowledge_proposals_batch_order
    ON public.knowledge_proposals(tenant_id,batch_id,ordinal);

CREATE TABLE public.knowledge_proposal_evidence (
    tenant_id uuid NOT NULL,
    proposal_id text NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal BETWEEN 0 AND 19),
    evidence_id text NOT NULL,
    PRIMARY KEY (tenant_id,proposal_id,ordinal),
    UNIQUE (tenant_id,proposal_id,evidence_id),
    FOREIGN KEY (tenant_id,proposal_id)
        REFERENCES public.knowledge_proposals(tenant_id,id),
    FOREIGN KEY (tenant_id,evidence_id)
        REFERENCES public.brain_evidence(tenant_id,id)
);

CREATE TABLE public.knowledge_proposal_decisions (
    tenant_id uuid NOT NULL,
    batch_id text NOT NULL,
    proposal_id text NOT NULL,
    decision text NOT NULL CHECK (decision IN ('approved','rejected')),
    reviewer_id uuid NOT NULL,
    reason text,
    publication_key uuid,
    object_kind text,
    object_id text,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,proposal_id),
    FOREIGN KEY (tenant_id,batch_id,proposal_id)
        REFERENCES public.knowledge_proposals(tenant_id,batch_id,id),
    FOREIGN KEY (tenant_id,reviewer_id,publication_key)
        REFERENCES public.knowledge_receipts(tenant_id,actor_id,idempotency_key),
    CHECK (
        (decision='approved' AND reason IS NULL AND publication_key IS NOT NULL
         AND object_kind IS NOT NULL AND object_id IS NOT NULL)
        OR
        (decision='rejected' AND reason IS NOT NULL AND length(reason) BETWEEN 1 AND 500
         AND publication_key IS NULL AND object_kind IS NULL AND object_id IS NULL)
    )
);

CREATE TABLE public.knowledge_proposal_review_receipts (
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
        REFERENCES public.knowledge_proposal_batches(tenant_id,id),
    CHECK (approved_count+rejected_count BETWEEN 1 AND 50)
);

-- Deferrable closure forbids a committed header with missing proposal/evidence rows.
CREATE FUNCTION public.require_knowledge_proposal_batch_complete() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
BEGIN
    IF (SELECT count(*) FROM public.knowledge_proposals p
        WHERE p.tenant_id=NEW.tenant_id AND p.batch_id=NEW.id) <> NEW.row_count THEN
        RAISE EXCEPTION 'incomplete knowledge proposal batch';
    END IF;
    RETURN NULL;
END
$function$;
CREATE CONSTRAINT TRIGGER knowledge_proposal_batch_complete
    AFTER INSERT ON public.knowledge_proposal_batches
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION public.require_knowledge_proposal_batch_complete();

CREATE FUNCTION public.require_knowledge_proposal_evidence_complete() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
BEGIN
    IF (SELECT count(*) FROM public.knowledge_proposal_evidence e
        WHERE e.tenant_id=NEW.tenant_id AND e.proposal_id=NEW.id) <> NEW.evidence_count THEN
        RAISE EXCEPTION 'incomplete knowledge proposal evidence';
    END IF;
    RETURN NULL;
END
$function$;
CREATE CONSTRAINT TRIGGER knowledge_proposal_evidence_complete
    AFTER INSERT ON public.knowledge_proposals
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION public.require_knowledge_proposal_evidence_complete();

CREATE FUNCTION public.guard_knowledge_proposal_decision() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
BEGIN
    IF NEW.decision='approved' AND NOT EXISTS (
        SELECT 1 FROM public.knowledge_receipts r
        WHERE r.tenant_id=NEW.tenant_id AND r.actor_id=NEW.reviewer_id
          AND r.idempotency_key=NEW.publication_key
          AND r.object_kind=NEW.object_kind AND r.object_id=NEW.object_id
    ) THEN
        RAISE EXCEPTION 'invalid knowledge proposal approval receipt';
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER knowledge_proposal_decision_basis
    BEFORE INSERT ON public.knowledge_proposal_decisions
    FOR EACH ROW EXECUTE FUNCTION public.guard_knowledge_proposal_decision();

CREATE FUNCTION public.require_knowledge_proposal_review_complete() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
DECLARE expected_count integer;
DECLARE actual_approved integer;
DECLARE actual_rejected integer;
BEGIN
    SELECT b.row_count INTO expected_count
    FROM public.knowledge_proposal_batches b
    WHERE b.tenant_id=NEW.tenant_id AND b.id=NEW.batch_id;
    SELECT count(*) FILTER (WHERE d.decision='approved'),
           count(*) FILTER (WHERE d.decision='rejected')
      INTO actual_approved,actual_rejected
    FROM public.knowledge_proposal_decisions d
    WHERE d.tenant_id=NEW.tenant_id AND d.batch_id=NEW.batch_id
      AND d.reviewer_id=NEW.reviewer_id;
    IF expected_count IS NULL OR actual_approved<>NEW.approved_count
       OR actual_rejected<>NEW.rejected_count
       OR actual_approved+actual_rejected<>expected_count THEN
        RAISE EXCEPTION 'incomplete knowledge proposal review';
    END IF;
    RETURN NULL;
END
$function$;
CREATE CONSTRAINT TRIGGER knowledge_proposal_review_complete
    AFTER INSERT ON public.knowledge_proposal_review_receipts
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION public.require_knowledge_proposal_review_complete();

CREATE FUNCTION public.require_knowledge_proposal_decision_review() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM public.knowledge_proposal_review_receipts r
        WHERE r.tenant_id=NEW.tenant_id AND r.batch_id=NEW.batch_id
          AND r.reviewer_id=NEW.reviewer_id
    ) THEN
        RAISE EXCEPTION 'knowledge proposal decision lacks review receipt';
    END IF;
    RETURN NULL;
END
$function$;
CREATE CONSTRAINT TRIGGER knowledge_proposal_decision_review
    AFTER INSERT ON public.knowledge_proposal_decisions
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION public.require_knowledge_proposal_decision_review();

DO $block$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'knowledge_proposal_batches','knowledge_proposals',
        'knowledge_proposal_evidence','knowledge_proposal_decisions',
        'knowledge_proposal_review_receipts'
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
