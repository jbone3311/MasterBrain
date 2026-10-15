BEGIN;

-- One reviewed publication of an exact, complete ADR-240 extraction.
CREATE TABLE public.brain_email_xlsx_document_bridge_receipts (
    tenant_id uuid NOT NULL,
    actor_id uuid NOT NULL,
    idempotency_key uuid NOT NULL,
    approval_id text NOT NULL,
    account_id uuid NOT NULL,
    attachment_id uuid NOT NULL,
    source_id text NOT NULL,
    item_id text NOT NULL,
    version_id text NOT NULL,
    evidence_id text NOT NULL,
    document_id text NOT NULL,
    normalizer text NOT NULL CHECK (normalizer ~
        '^email-xlsx-v1:sandbox-fileos-document-v1-[a-f0-9]{64}:synthetic-unscanned-xlsx-v1$'),
    text_sha256 text NOT NULL CHECK (text_sha256 ~ '^[a-f0-9]{64}$'),
    chunk_count integer NOT NULL CHECK (chunk_count BETWEEN 1 AND 512),
    code_revision text NOT NULL CHECK (length(code_revision) BETWEEN 1 AND 200),
    request_hash text NOT NULL CHECK (request_hash ~ '^[a-f0-9]{64}$'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,actor_id,idempotency_key),
    UNIQUE (tenant_id,approval_id),
    UNIQUE (tenant_id,document_id),
    FOREIGN KEY (tenant_id,approval_id)
        REFERENCES public.brain_email_xlsx_extraction_results(tenant_id,approval_id),
    FOREIGN KEY (tenant_id,account_id,attachment_id)
        REFERENCES public.attachment_receipts(tenant_id,account_id,id),
    FOREIGN KEY (tenant_id,source_id,item_id,version_id)
        REFERENCES public.brain_source_versions(tenant_id,source_id,item_id,id),
    FOREIGN KEY (tenant_id,evidence_id) REFERENCES public.brain_evidence(tenant_id,id),
    FOREIGN KEY (tenant_id,document_id)
        REFERENCES public.brain_normalized_documents(tenant_id,id)
);

-- SECURITY INVOKER preserves all underlying forced tenant RLS. An approval's
-- expiry authorizes publication but does not later invalidate a current document.
CREATE FUNCTION public.brain_email_xlsx_basis_current(
    target_tenant uuid, target_approval text, target_evidence text
) RETURNS boolean LANGUAGE sql STABLE SECURITY INVOKER
SET search_path=pg_catalog,public AS $function$
    SELECT EXISTS (
        SELECT 1 FROM public.brain_email_xlsx_extraction_approvals ap
        JOIN public.brain_email_xlsx_extraction_results r
          ON r.tenant_id=ap.tenant_id AND r.approval_id=ap.id
        JOIN public.attachment_receipts ar
          ON ar.tenant_id=ap.tenant_id AND ar.account_id=ap.account_id
         AND ar.id=ap.attachment_id AND ar.evidence_id=ap.parent_version_id
        JOIN public.message_versions mv
          ON mv.tenant_id=ar.tenant_id AND mv.account_id=ar.account_id
         AND mv.id=ar.evidence_id
        JOIN public.messages m
          ON m.tenant_id=mv.tenant_id AND m.account_id=mv.account_id
         AND m.id=mv.message_id
        JOIN public.message_sync_state ms
          ON ms.tenant_id=m.tenant_id AND ms.account_id=m.account_id
         AND ms.provider_id=m.provider_message_id
        JOIN public.mail_accounts a
          ON a.tenant_id=mv.tenant_id AND a.id=mv.account_id
        JOIN public.brain_email_attachment_bridge_receipts ab
          ON ab.tenant_id=ar.tenant_id AND ab.account_id=ar.account_id
         AND ab.legacy_attachment_id=ar.id
         AND ab.legacy_parent_version_id=mv.id
        JOIN public.brain_source_items ai
          ON ai.tenant_id=ab.tenant_id AND ai.id=ab.item_id
         AND ai.current_version_id=ab.version_id
        JOIN public.brain_sources s
          ON s.tenant_id=ab.tenant_id AND s.id=ab.source_id
         AND s.id=ai.source_id
        JOIN public.brain_email_bridge_receipts eb
          ON eb.tenant_id=mv.tenant_id AND eb.account_id=mv.account_id
         AND eb.legacy_version_id=mv.id
         AND eb.evidence_id=ab.parent_evidence_id
        JOIN public.brain_source_items pi
          ON pi.tenant_id=eb.tenant_id AND pi.id=eb.item_id
         AND pi.current_version_id=eb.version_id
        WHERE ap.tenant_id=target_tenant AND ap.id=target_approval
          AND ab.evidence_id=target_evidence AND ab.source_id=ap.source_id
          AND ar.part_id=ap.part_path AND ar.sha256=ap.part_sha256
          AND ar.byte_size=ap.part_size_bytes
          AND ar.media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
          AND right(lower(ar.safe_filename),5)='.xlsx'
          AND mv.raw_sha256=ap.raw_sha256
          AND m.raw_sha256=mv.raw_sha256 AND m.parser_version=mv.parser_version
          AND NOT m.deleted AND NOT m.quarantined
          AND ms.status='ready' AND ms.event_key=ap.source_event_key
          AND a.status='active' AND a.provider_account_id IS NULL
          AND a.secret_ref LIKE 'synthetic:%'
          AND s.kind='email' AND s.status='active'
          AND NOT public.brain_email_evidence_is_excluded(ab.tenant_id,ab.evidence_id)
    );
$function$;

CREATE FUNCTION public.brain_email_xlsx_document_is_current(
    target_tenant uuid, target_document text
) RETURNS boolean LANGUAGE sql STABLE SECURITY INVOKER
SET search_path=pg_catalog,public AS $function$
    SELECT EXISTS (
        SELECT 1 FROM public.brain_email_xlsx_document_bridge_receipts b
        WHERE b.tenant_id=target_tenant AND b.document_id=target_document
          AND public.brain_email_xlsx_basis_current(
              b.tenant_id,b.approval_id,b.evidence_id)
    );
$function$;

CREATE FUNCTION public.guard_email_xlsx_document_bridge() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
BEGIN
    IF NEW.actor_id IS DISTINCT FROM
       nullif(current_setting('email_brain.actor_id',true),'')::uuid THEN
        RAISE EXCEPTION 'Email XLSX bridge actor context mismatch';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM public.brain_email_xlsx_extraction_results r
        JOIN public.brain_email_xlsx_extraction_approvals ap
          ON ap.tenant_id=r.tenant_id AND ap.id=r.approval_id
        JOIN public.brain_email_attachment_bridge_receipts ab
          ON ab.tenant_id=r.tenant_id AND ab.account_id=r.account_id
         AND ab.legacy_attachment_id=r.attachment_id
        JOIN public.brain_normalized_documents d
          ON d.tenant_id=ab.tenant_id AND d.id=NEW.document_id
        WHERE r.tenant_id=NEW.tenant_id AND r.approval_id=NEW.approval_id
          AND ap.expires_at>clock_timestamp()
          AND r.account_id=NEW.account_id AND r.attachment_id=NEW.attachment_id
          AND ab.source_id=NEW.source_id AND ab.item_id=NEW.item_id
          AND ab.version_id=NEW.version_id AND ab.evidence_id=NEW.evidence_id
          AND d.evidence_id=ab.evidence_id AND d.normalizer=NEW.normalizer
          AND d.body_sha256=r.text_sha256 AND d.body=r.extracted_text
          AND NEW.text_sha256=r.text_sha256
          AND NEW.normalizer='email-xlsx-v1:'||r.processor_version||':'||ap.policy_version
          AND (SELECT count(*) FROM public.brain_chunks c
               WHERE c.tenant_id=d.tenant_id AND c.document_id=d.id)=NEW.chunk_count
          AND public.brain_email_xlsx_basis_current(
              r.tenant_id,r.approval_id,ab.evidence_id)
    ) THEN
        RAISE EXCEPTION 'invalid Email XLSX document bridge basis';
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER email_xlsx_document_bridge_basis
    BEFORE INSERT ON public.brain_email_xlsx_document_bridge_receipts
    FOR EACH ROW EXECUTE FUNCTION public.guard_email_xlsx_document_bridge();

ALTER TABLE public.brain_email_xlsx_document_bridge_receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.brain_email_xlsx_document_bridge_receipts FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON public.brain_email_xlsx_document_bridge_receipts USING
    (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid)
    WITH CHECK (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid);
CREATE POLICY tenant_login_fence ON public.brain_email_xlsx_document_bridge_receipts
    AS RESTRICTIVE FOR ALL TO PUBLIC
    USING (public.masterbrain_tenant_login_allows(tenant_id))
    WITH CHECK (public.masterbrain_tenant_login_allows(tenant_id));
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE
    ON public.brain_email_xlsx_document_bridge_receipts
    FOR EACH ROW EXECUTE FUNCTION public.deny_evidence_mutation();
CREATE TRIGGER protected_no_truncate BEFORE TRUNCATE
    ON public.brain_email_xlsx_document_bridge_receipts
    FOR EACH STATEMENT EXECUTE FUNCTION public.deny_protected_truncate();

COMMIT;
