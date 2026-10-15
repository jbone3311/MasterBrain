BEGIN;

-- ADR-218: a point-in-time worker replay of one reviewed FileOS text source.
-- No PDF/OCR completeness, current-on-disk guarantee or financial approval.
CREATE TABLE public.knowledge_source_tier_fileos_replays (
    tenant_id uuid NOT NULL,
    review_id text NOT NULL,
    evidence_id text NOT NULL,
    document_id text NOT NULL,
    source_version_id text NOT NULL,
    source_id text NOT NULL,
    actor_id uuid NOT NULL,
    source_sha256 text NOT NULL CHECK (source_sha256 ~ '^[a-f0-9]{64}$'),
    source_size_bytes bigint NOT NULL CHECK (source_size_bytes BETWEEN 1 AND 1048576),
    text_sha256 text NOT NULL CHECK (text_sha256 ~ '^[a-f0-9]{64}$'),
    normalizer text NOT NULL CHECK (normalizer='fileos-text-v1'),
    root_binding_sha256 text NOT NULL CHECK (root_binding_sha256 ~ '^[a-f0-9]{64}$'),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,review_id),
    FOREIGN KEY (tenant_id,review_id)
        REFERENCES public.knowledge_source_tier_reviews(tenant_id,id),
    FOREIGN KEY (tenant_id,evidence_id)
        REFERENCES public.brain_evidence(tenant_id,id),
    FOREIGN KEY (tenant_id,document_id)
        REFERENCES public.brain_normalized_documents(tenant_id,id),
    FOREIGN KEY (tenant_id,source_version_id)
        REFERENCES public.brain_source_versions(tenant_id,id),
    FOREIGN KEY (tenant_id,source_id)
        REFERENCES public.brain_sources(tenant_id,id)
);

CREATE FUNCTION public.guard_source_tier_fileos_replay() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
BEGIN
    IF NEW.actor_id<>nullif(current_setting('email_brain.actor_id',true),'')::uuid THEN
        RAISE EXCEPTION 'source tier FileOS replay actor context mismatch';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM public.knowledge_source_tier_reviews r
        JOIN public.brain_normalized_documents d
          ON d.tenant_id=r.tenant_id AND d.id=r.document_id
        JOIN public.brain_evidence e
          ON e.tenant_id=d.tenant_id AND e.id=d.evidence_id
        JOIN public.brain_source_versions v
          ON v.tenant_id=e.tenant_id AND v.id=e.source_version_id
        JOIN public.brain_source_items i
          ON i.tenant_id=v.tenant_id AND i.id=v.item_id AND i.source_id=v.source_id
        JOIN public.brain_sources s
          ON s.tenant_id=i.tenant_id AND s.id=i.source_id
        WHERE r.tenant_id=NEW.tenant_id AND r.id=NEW.review_id
          AND r.evidence_id=NEW.evidence_id AND r.document_id=NEW.document_id
          AND r.source_version_id=NEW.source_version_id
          AND r.source_sha256=NEW.source_sha256
          AND r.document_sha256=NEW.text_sha256
          AND d.body_sha256=NEW.text_sha256 AND d.normalizer=NEW.normalizer
          AND e.source_version_id=NEW.source_version_id
          AND e.sha256=NEW.source_sha256
          AND v.sha256=NEW.source_sha256 AND v.size_bytes=NEW.source_size_bytes
          AND i.current_version_id=v.id
          AND s.id=NEW.source_id AND s.kind='fileos' AND s.status='active'
          AND s.root_binding_sha256=NEW.root_binding_sha256
          AND NOT public.brain_email_evidence_is_excluded(e.tenant_id,e.id)
          AND pg_catalog.strpos(d.body,r.source_quote)>0
    ) THEN
        RAISE EXCEPTION 'invalid source tier FileOS replay basis';
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER source_tier_fileos_replay_basis
    BEFORE INSERT ON public.knowledge_source_tier_fileos_replays
    FOR EACH ROW EXECUTE FUNCTION public.guard_source_tier_fileos_replay();

ALTER TABLE public.knowledge_source_tier_fileos_replays ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.knowledge_source_tier_fileos_replays FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON public.knowledge_source_tier_fileos_replays USING
    (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid)
    WITH CHECK (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid);
CREATE POLICY tenant_login_fence ON public.knowledge_source_tier_fileos_replays
    AS RESTRICTIVE FOR ALL TO PUBLIC
    USING (public.masterbrain_tenant_login_allows(tenant_id))
    WITH CHECK (public.masterbrain_tenant_login_allows(tenant_id));
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE
    ON public.knowledge_source_tier_fileos_replays
    FOR EACH ROW EXECUTE FUNCTION public.deny_evidence_mutation();
CREATE TRIGGER protected_no_truncate BEFORE TRUNCATE
    ON public.knowledge_source_tier_fileos_replays
    FOR EACH STATEMENT EXECUTE FUNCTION public.deny_protected_truncate();

COMMIT;
