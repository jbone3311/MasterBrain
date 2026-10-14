BEGIN;

-- ADR-172: private source-linked proposals, not reviewed KnowledgeCore facts.
CREATE TABLE public.knowledge_statement_proposals (
    tenant_id uuid NOT NULL,
    id text NOT NULL CHECK (id ~ '^statement_[a-f0-9]{32}$'),
    document_id text NOT NULL,
    evidence_id text NOT NULL,
    source_version_id text NOT NULL,
    source_id text NOT NULL,
    source_kind text NOT NULL CHECK (source_kind IN ('email','fileos')),
    recipe text NOT NULL CHECK (recipe='streetbeat'),
    donor_commit text NOT NULL CHECK (donor_commit ~ '^[a-f0-9]{40}$'),
    transform_version text NOT NULL CHECK (length(transform_version) BETWEEN 1 AND 100),
    text_sha256 text NOT NULL CHECK (text_sha256 ~ '^[a-f0-9]{64}$'),
    source_sha256 text NOT NULL CHECK (source_sha256 ~ '^[a-f0-9]{64}$'),
    account_number text CHECK (account_number IS NULL OR length(account_number) BETWEEN 1 AND 64),
    period text CHECK (period IS NULL OR period ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
    status text NOT NULL CHECK (status IN ('reconciled','mismatch','unreconciled','incomplete')),
    coverage_errors text[] NOT NULL CHECK (
        array_ndims(coverage_errors) IS NULL OR array_ndims(coverage_errors)=1
    ) CHECK (
        array_position(coverage_errors,NULL) IS NULL
        AND coverage_errors <@ ARRAY[
            'missing_period','invalid_period','missing_account','invalid_date',
            'unparsed_transaction_line','unparsed_holding_line','no_rows'
        ]::text[]
    ),
    row_count integer NOT NULL CHECK (row_count BETWEEN 0 AND 2000),
    rows_sha256 text NOT NULL CHECK (rows_sha256 ~ '^[a-f0-9]{64}$'),
    expected numeric(38,12),
    actual numeric(38,12),
    delta numeric(38,12) CHECK (delta IS NULL OR delta>=0),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    UNIQUE (tenant_id,document_id,transform_version),
    FOREIGN KEY (tenant_id,document_id) REFERENCES public.brain_normalized_documents(tenant_id,id),
    FOREIGN KEY (tenant_id,evidence_id) REFERENCES public.brain_evidence(tenant_id,id),
    FOREIGN KEY (tenant_id,source_version_id) REFERENCES public.brain_source_versions(tenant_id,id),
    FOREIGN KEY (tenant_id,source_id) REFERENCES public.brain_sources(tenant_id,id),
    CHECK ((status='incomplete')=(cardinality(coverage_errors)>0)),
    CHECK (status NOT IN ('reconciled','mismatch') OR
           (row_count>0 AND expected IS NOT NULL AND actual IS NOT NULL AND delta IS NOT NULL))
);
CREATE INDEX knowledge_statement_proposals_document
    ON public.knowledge_statement_proposals(tenant_id,document_id,recorded_at DESC);

CREATE TABLE public.knowledge_statement_rows (
    tenant_id uuid NOT NULL,
    proposal_id text NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal BETWEEN 0 AND 1999),
    row_type text NOT NULL CHECK (row_type IN ('holding','transaction')),
    description text NOT NULL CHECK (length(description) BETWEEN 1 AND 300),
    symbol text CHECK (symbol IS NULL OR length(symbol) BETWEEN 1 AND 40),
    line_date date,
    quantity numeric(38,12),
    price numeric(38,12),
    amount numeric(38,12) NOT NULL,
    cost_basis numeric(38,12),
    unrealized numeric(38,12),
    currency text NOT NULL CHECK (currency='USD'),
    text_start integer NOT NULL CHECK (text_start>=0),
    text_end integer NOT NULL CHECK (text_end>text_start AND text_end<=1048576),
    PRIMARY KEY (tenant_id,proposal_id,ordinal),
    FOREIGN KEY (tenant_id,proposal_id)
        REFERENCES public.knowledge_statement_proposals(tenant_id,id)
);

CREATE TABLE public.knowledge_statement_receipts (
    tenant_id uuid NOT NULL,
    actor_id uuid NOT NULL,
    idempotency_key uuid NOT NULL,
    request_sha256 text NOT NULL CHECK (request_sha256 ~ '^[a-f0-9]{64}$'),
    proposal_id text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,actor_id,idempotency_key),
    FOREIGN KEY (tenant_id,proposal_id)
        REFERENCES public.knowledge_statement_proposals(tenant_id,id)
);

-- Refuse a direct SQL writer's mismatched cross-table identity or stale source.
CREATE FUNCTION public.guard_statement_proposal_basis() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM public.brain_normalized_documents AS d
        JOIN public.brain_evidence AS e
          ON e.tenant_id=d.tenant_id AND e.id=d.evidence_id
        JOIN public.brain_source_versions AS v
          ON v.tenant_id=e.tenant_id AND v.id=e.source_version_id
        JOIN public.brain_source_items AS i
          ON i.tenant_id=v.tenant_id AND i.id=v.item_id AND i.source_id=v.source_id
        JOIN public.brain_sources AS s
          ON s.tenant_id=i.tenant_id AND s.id=i.source_id
        WHERE d.tenant_id=NEW.tenant_id AND d.id=NEW.document_id
          AND d.evidence_id=NEW.evidence_id AND d.body_sha256=NEW.text_sha256
          AND e.source_version_id=NEW.source_version_id AND e.sha256=NEW.source_sha256
          AND v.sha256=NEW.source_sha256 AND i.current_version_id=v.id
          AND s.id=NEW.source_id AND s.kind=NEW.source_kind AND s.status='active'
    ) THEN
        RAISE EXCEPTION 'invalid statement proposal basis';
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER statement_proposal_basis BEFORE INSERT ON public.knowledge_statement_proposals
    FOR EACH ROW EXECUTE FUNCTION public.guard_statement_proposal_basis();

CREATE FUNCTION public.guard_statement_row_bounds() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
DECLARE allowed_count integer;
DECLARE body_length integer;
BEGIN
    SELECT p.row_count,pg_catalog.char_length(d.body) INTO allowed_count,body_length
    FROM public.knowledge_statement_proposals AS p
    JOIN public.brain_normalized_documents AS d
      ON d.tenant_id=p.tenant_id AND d.id=p.document_id
    WHERE p.tenant_id=NEW.tenant_id AND p.id=NEW.proposal_id;
    IF allowed_count IS NULL OR NEW.ordinal>=allowed_count OR NEW.text_end>body_length THEN
        RAISE EXCEPTION 'invalid statement row basis';
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER statement_row_bounds BEFORE INSERT ON public.knowledge_statement_rows
    FOR EACH ROW EXECUTE FUNCTION public.guard_statement_row_bounds();

CREATE FUNCTION public.require_statement_rows_complete() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
BEGIN
    IF (SELECT count(*) FROM public.knowledge_statement_rows AS r
        WHERE r.tenant_id=NEW.tenant_id AND r.proposal_id=NEW.id) <> NEW.row_count THEN
        RAISE EXCEPTION 'incomplete statement proposal';
    END IF;
    RETURN NULL;
END
$function$;
CREATE CONSTRAINT TRIGGER statement_rows_complete
    AFTER INSERT ON public.knowledge_statement_proposals
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION public.require_statement_rows_complete();

DO $block$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'knowledge_statement_proposals','knowledge_statement_rows','knowledge_statement_receipts'
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
