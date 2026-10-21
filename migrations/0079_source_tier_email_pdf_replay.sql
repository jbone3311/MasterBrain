BEGIN;

-- ADR-229: one reviewed, occurrence-specific Email PDF text-layer replay.
CREATE TABLE public.knowledge_source_tier_email_pdf_replays (
    tenant_id uuid NOT NULL,
    review_id text NOT NULL,
    evidence_id text NOT NULL,
    document_id text NOT NULL,
    source_version_id text NOT NULL,
    source_id text NOT NULL,
    account_id uuid NOT NULL,
    parent_version_id uuid NOT NULL,
    legacy_attachment_id uuid NOT NULL,
    legacy_extraction_id uuid NOT NULL,
    actor_id uuid NOT NULL,
    raw_sha256 text NOT NULL CHECK (raw_sha256 ~ '^[a-f0-9]{64}$'),
    raw_size_bytes bigint NOT NULL CHECK (raw_size_bytes BETWEEN 1 AND 16777216),
    part_path text NOT NULL CHECK (part_path ~ '^1(\.[1-9][0-9]{0,3}){0,20}$'),
    part_sha256 text NOT NULL CHECK (part_sha256 ~ '^[a-f0-9]{64}$'),
    part_size_bytes bigint NOT NULL CHECK (part_size_bytes BETWEEN 1 AND 4194304),
    text_sha256 text NOT NULL CHECK (text_sha256 ~ '^[a-f0-9]{64}$'),
    normalizer text NOT NULL CHECK (
        normalizer ~ '^email-pdf-v1:sandbox-pdf-v1-[a-f0-9]{64}:synthetic-unscanned-pdf-v1$'
    ),
    result_sha256 text NOT NULL CHECK (result_sha256 ~ '^[a-f0-9]{64}$'),
    page_count integer NOT NULL CHECK (page_count BETWEEN 1 AND 40),
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
        REFERENCES public.brain_sources(tenant_id,id),
    FOREIGN KEY (tenant_id,account_id)
        REFERENCES public.mail_accounts(tenant_id,id),
    FOREIGN KEY (tenant_id,parent_version_id)
        REFERENCES public.message_versions(tenant_id,id),
    FOREIGN KEY (tenant_id,legacy_attachment_id)
        REFERENCES public.attachment_receipts(tenant_id,id),
    FOREIGN KEY (tenant_id,legacy_extraction_id)
        REFERENCES public.document_extractions(tenant_id,id)
);

CREATE FUNCTION public.guard_source_tier_email_pdf_replay() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
BEGIN
    IF NEW.actor_id<>nullif(current_setting('email_brain.actor_id',true),'')::uuid THEN
        RAISE EXCEPTION 'source tier Email PDF replay actor context mismatch';
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
        JOIN public.brain_email_attachment_bridge_receipts ab
          ON ab.tenant_id=e.tenant_id AND ab.evidence_id=e.id
         AND ab.version_id=v.id AND ab.item_id=i.id AND ab.source_id=s.id
        JOIN public.brain_parts bp
          ON bp.tenant_id=ab.tenant_id AND bp.id=ab.part_id
         AND bp.evidence_id=e.id AND bp.parent_evidence_id=ab.parent_evidence_id
        JOIN public.brain_email_document_bridge_receipts db
          ON db.tenant_id=d.tenant_id AND db.document_id=d.id
         AND db.evidence_id=e.id AND db.version_id=v.id
         AND db.source_id=s.id AND db.item_id=i.id
         AND db.legacy_attachment_id=ab.legacy_attachment_id
        JOIN public.attachment_receipts ar
          ON ar.tenant_id=ab.tenant_id AND ar.id=ab.legacy_attachment_id
         AND ar.account_id=ab.account_id
         AND ar.evidence_id=ab.legacy_parent_version_id
        JOIN public.document_extractions de
          ON de.tenant_id=db.tenant_id AND de.id=db.legacy_extraction_id
         AND de.receipt_id=ar.id AND de.account_id=ar.account_id
        JOIN public.document_jobs dj
          ON dj.tenant_id=db.tenant_id AND dj.id=db.legacy_approval_job_id
         AND dj.extraction_id=de.id AND dj.receipt_id=ar.id
         AND dj.processor_version=de.processor_version
         AND dj.policy_version=de.policy_version
        JOIN public.message_versions mv
          ON mv.tenant_id=ar.tenant_id AND mv.id=ar.evidence_id
         AND mv.account_id=ar.account_id
        JOIN public.messages m
          ON m.tenant_id=mv.tenant_id AND m.id=mv.message_id
         AND m.account_id=mv.account_id
        JOIN public.mail_accounts a
          ON a.tenant_id=mv.tenant_id AND a.id=mv.account_id
        JOIN public.raw_objects ro
          ON ro.tenant_id=mv.tenant_id AND ro.account_id=mv.account_id
         AND ro.sha256=mv.raw_sha256
        JOIN public.brain_email_bridge_receipts eb
          ON eb.tenant_id=mv.tenant_id AND eb.legacy_version_id=mv.id
         AND eb.account_id=mv.account_id AND eb.evidence_id=ab.parent_evidence_id
        JOIN public.brain_source_items pi
          ON pi.tenant_id=eb.tenant_id AND pi.id=eb.item_id
         AND pi.current_version_id=eb.version_id
        WHERE r.tenant_id=NEW.tenant_id AND r.id=NEW.review_id
          AND r.evidence_id=NEW.evidence_id AND r.document_id=NEW.document_id
          AND r.source_version_id=NEW.source_version_id
          AND r.source_sha256=NEW.part_sha256
          AND r.document_sha256=NEW.text_sha256
          AND d.body_sha256=NEW.text_sha256 AND d.normalizer=NEW.normalizer
          AND d.body=de.extracted_text
          AND e.source_version_id=NEW.source_version_id
          AND e.sha256=NEW.part_sha256 AND e.storage='source_bound' AND NOT e.retained
          AND v.sha256=NEW.part_sha256 AND v.size_bytes=NEW.part_size_bytes
          AND v.media_type='application/pdf' AND i.current_version_id=v.id
          AND s.id=NEW.source_id AND s.kind='email' AND s.status='active'
          AND ab.account_id=NEW.account_id
          AND ab.legacy_parent_version_id=NEW.parent_version_id
          AND ab.legacy_attachment_id=NEW.legacy_attachment_id
          AND bp.part_path=NEW.part_path AND bp.sha256=NEW.part_sha256
          AND bp.size_bytes=NEW.part_size_bytes
          AND bp.media_type='application/pdf' AND bp.status='deferred'
          AND ar.part_id=NEW.part_path AND ar.sha256=NEW.part_sha256
          AND ar.byte_size=NEW.part_size_bytes AND ar.media_type='application/pdf'
          AND ar.status='deferred'
          AND db.account_id=NEW.account_id
          AND db.legacy_extraction_id=NEW.legacy_extraction_id
          AND db.extraction_status='extracted'
          AND db.processor_version=de.processor_version
          AND db.policy_version=de.policy_version
          AND db.normalizer=NEW.normalizer
          AND db.result_sha256=NEW.result_sha256
          AND db.extraction_revision=de.revision
          AND de.status='extracted' AND de.reason='bounded_pdf_v1'
          AND jsonb_array_length(de.result->'pages')=NEW.page_count
          AND dj.status='completed' AND dj.outcome='result_saved'
          AND mv.id=NEW.parent_version_id AND mv.raw_sha256=NEW.raw_sha256
          AND m.raw_sha256=mv.raw_sha256
          AND m.parser_version=mv.parser_version
          AND NOT m.deleted AND NOT m.quarantined
          AND a.status='active' AND ro.raw_size=NEW.raw_size_bytes
          AND NOT public.brain_email_evidence_is_excluded(e.tenant_id,e.id)
          AND pg_catalog.strpos(d.body,r.source_quote)>0
    ) THEN
        RAISE EXCEPTION 'invalid source tier Email PDF replay basis';
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER source_tier_email_pdf_replay_basis
    BEFORE INSERT ON public.knowledge_source_tier_email_pdf_replays
    FOR EACH ROW EXECUTE FUNCTION public.guard_source_tier_email_pdf_replay();

ALTER TABLE public.knowledge_source_tier_email_pdf_replays ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.knowledge_source_tier_email_pdf_replays FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON public.knowledge_source_tier_email_pdf_replays USING
    (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid)
    WITH CHECK (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid);
CREATE POLICY tenant_login_fence ON public.knowledge_source_tier_email_pdf_replays
    AS RESTRICTIVE FOR ALL TO PUBLIC
    USING (public.masterbrain_tenant_login_allows(tenant_id))
    WITH CHECK (public.masterbrain_tenant_login_allows(tenant_id));
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE
    ON public.knowledge_source_tier_email_pdf_replays
    FOR EACH ROW EXECUTE FUNCTION public.deny_evidence_mutation();
CREATE TRIGGER protected_no_truncate BEFORE TRUNCATE
    ON public.knowledge_source_tier_email_pdf_replays
    FOR EACH STATEMENT EXECUTE FUNCTION public.deny_protected_truncate();

COMMIT;
