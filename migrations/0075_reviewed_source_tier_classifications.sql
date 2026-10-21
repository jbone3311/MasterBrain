BEGIN;

-- ADR-217: human-reviewed document authority, pinned to the current source
-- version and normalized text. This is NOT independent source-byte attestation.
CREATE TABLE public.knowledge_source_tier_reviews (
    tenant_id uuid NOT NULL,
    id text NOT NULL CHECK (id ~ '^stier_[a-f0-9]{32}$'),
    evidence_id text NOT NULL,
    source_version_id text NOT NULL,
    source_sha256 text NOT NULL CHECK (source_sha256 ~ '^[a-f0-9]{64}$'),
    document_id text NOT NULL,
    document_sha256 text NOT NULL CHECK (document_sha256 ~ '^[a-f0-9]{64}$'),
    source_tier text NOT NULL CHECK (source_tier IN ('T1','T2','T3')),
    authority_kind text NOT NULL CHECK (
        (source_tier='T1' AND authority_kind IN ('signed_instrument','regulatory_filing'))
        OR (source_tier='T2' AND authority_kind IN ('issuer_statement','administrator_statement'))
        OR (source_tier='T3' AND authority_kind IN ('internal_record','other'))
    ),
    source_quote text NOT NULL CHECK (
        length(source_quote) BETWEEN 1 AND 2000 AND source_quote ~ '[^[:space:]]'
    ),
    reviewer_id uuid NOT NULL,
    idempotency_key uuid NOT NULL,
    request_sha256 text NOT NULL CHECK (request_sha256 ~ '^[a-f0-9]{64}$'),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,id),
    UNIQUE (tenant_id,reviewer_id,idempotency_key),
    FOREIGN KEY (tenant_id,evidence_id) REFERENCES public.brain_evidence(tenant_id,id),
    FOREIGN KEY (tenant_id,source_version_id)
        REFERENCES public.brain_source_versions(tenant_id,id),
    FOREIGN KEY (tenant_id,document_id)
        REFERENCES public.brain_normalized_documents(tenant_id,id)
);
CREATE INDEX knowledge_source_tier_reviews_evidence
    ON public.knowledge_source_tier_reviews(tenant_id,evidence_id,recorded_at DESC,id DESC);

CREATE FUNCTION public.guard_source_tier_review() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
BEGIN
    IF NEW.reviewer_id<>nullif(current_setting('email_brain.actor_id',true),'')::uuid THEN
        RAISE EXCEPTION 'source tier reviewer context mismatch';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM public.brain_normalized_documents d
        JOIN public.brain_evidence e
          ON e.tenant_id=d.tenant_id AND e.id=d.evidence_id
        JOIN public.brain_source_versions v
          ON v.tenant_id=e.tenant_id AND v.id=e.source_version_id
        JOIN public.brain_source_items i
          ON i.tenant_id=v.tenant_id AND i.id=v.item_id AND i.source_id=v.source_id
        JOIN public.brain_sources s
          ON s.tenant_id=i.tenant_id AND s.id=i.source_id
        WHERE d.tenant_id=NEW.tenant_id AND d.id=NEW.document_id
          AND d.evidence_id=NEW.evidence_id AND d.body_sha256=NEW.document_sha256
          AND e.source_version_id=NEW.source_version_id
          AND e.sha256=NEW.source_sha256 AND v.sha256=NEW.source_sha256
          AND i.current_version_id=v.id AND s.status='active'
          AND NOT public.brain_email_evidence_is_excluded(e.tenant_id,e.id)
          AND pg_catalog.strpos(d.body,NEW.source_quote)>0
    ) THEN
        RAISE EXCEPTION 'invalid source tier review basis';
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER source_tier_review_basis
    BEFORE INSERT ON public.knowledge_source_tier_reviews
    FOR EACH ROW EXECUTE FUNCTION public.guard_source_tier_review();

ALTER TABLE public.knowledge_source_tier_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.knowledge_source_tier_reviews FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON public.knowledge_source_tier_reviews USING
    (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid)
    WITH CHECK (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid);
CREATE POLICY tenant_login_fence ON public.knowledge_source_tier_reviews AS RESTRICTIVE
    FOR ALL TO PUBLIC USING (public.masterbrain_tenant_login_allows(tenant_id))
    WITH CHECK (public.masterbrain_tenant_login_allows(tenant_id));
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON public.knowledge_source_tier_reviews
    FOR EACH ROW EXECUTE FUNCTION public.deny_evidence_mutation();
CREATE TRIGGER protected_no_truncate BEFORE TRUNCATE ON public.knowledge_source_tier_reviews
    FOR EACH STATEMENT EXECUTE FUNCTION public.deny_protected_truncate();

COMMIT;
