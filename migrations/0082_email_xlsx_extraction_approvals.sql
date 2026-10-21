BEGIN;

-- Human permission to extract one exact synthetic Email XLSX occurrence.
-- This is not a PDF job, extraction result, document bridge or source-tier review.
CREATE TABLE public.brain_email_xlsx_extraction_approvals (
    tenant_id uuid NOT NULL,
    id text NOT NULL CHECK (id ~ '^xapp_[a-f0-9]{32}$'),
    actor_id uuid NOT NULL,
    idempotency_key uuid NOT NULL,
    account_id uuid NOT NULL,
    parent_version_id uuid NOT NULL,
    attachment_id uuid NOT NULL,
    source_id text NOT NULL,
    source_event_key text NOT NULL,
    raw_sha256 text NOT NULL CHECK (raw_sha256 ~ '^[a-f0-9]{64}$'),
    raw_size_bytes bigint NOT NULL CHECK (raw_size_bytes BETWEEN 1 AND 16777216),
    part_path text NOT NULL CHECK (part_path ~ '^1(\.[1-9][0-9]{0,3}){0,20}$'),
    part_sha256 text NOT NULL CHECK (part_sha256 ~ '^[a-f0-9]{64}$'),
    part_size_bytes bigint NOT NULL CHECK (part_size_bytes BETWEEN 1 AND 8388608),
    processor_version text NOT NULL CHECK (
        processor_version ~ '^sandbox-fileos-document-v1-[a-f0-9]{64}$'),
    policy_version text NOT NULL CHECK (policy_version='synthetic-unscanned-xlsx-v1'),
    request_sha256 text NOT NULL CHECK (request_sha256 ~ '^[a-f0-9]{64}$'),
    created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
    expires_at timestamptz NOT NULL DEFAULT statement_timestamp()+interval '1 hour',
    PRIMARY KEY (tenant_id,id),
    UNIQUE (tenant_id,actor_id,idempotency_key),
    FOREIGN KEY (tenant_id,account_id) REFERENCES public.mail_accounts(tenant_id,id),
    FOREIGN KEY (tenant_id,account_id,parent_version_id)
        REFERENCES public.message_versions(tenant_id,account_id,id),
    FOREIGN KEY (tenant_id,account_id,attachment_id)
        REFERENCES public.attachment_receipts(tenant_id,account_id,id),
    FOREIGN KEY (tenant_id,source_id) REFERENCES public.brain_sources(tenant_id,id),
    CHECK (expires_at=created_at+interval '1 hour')
);

CREATE FUNCTION public.guard_email_xlsx_extraction_approval() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
BEGIN
    IF NEW.actor_id IS DISTINCT FROM
       nullif(current_setting('email_brain.actor_id',true),'')::uuid THEN
        RAISE EXCEPTION 'Email XLSX approval actor context mismatch';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM public.attachment_receipts ar
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
        JOIN public.raw_objects ro
          ON ro.tenant_id=mv.tenant_id AND ro.account_id=mv.account_id
         AND ro.sha256=mv.raw_sha256
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
        WHERE ar.tenant_id=NEW.tenant_id AND ar.id=NEW.attachment_id
          AND ar.account_id=NEW.account_id AND mv.id=NEW.parent_version_id
          AND ar.part_id=NEW.part_path AND ar.sha256=NEW.part_sha256
          AND ar.byte_size=NEW.part_size_bytes
          AND ar.media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
          AND right(lower(ar.safe_filename),5)='.xlsx'
          AND ar.status='deferred' AND ar.reason IN
              ('isolated_extractor_required','extraction_byte_limit')
          AND mv.raw_sha256=NEW.raw_sha256 AND ro.raw_size=NEW.raw_size_bytes
          AND m.raw_sha256=mv.raw_sha256 AND m.parser_version=mv.parser_version
          AND NOT m.deleted AND NOT m.quarantined
          AND ms.status='ready' AND ms.event_key=NEW.source_event_key
          AND a.status='active' AND a.provider_account_id IS NULL
          AND a.secret_ref LIKE 'synthetic:%'
          AND s.id=NEW.source_id AND s.kind='email' AND s.status='active'
          AND NOT public.brain_email_evidence_is_excluded(ab.tenant_id,ab.evidence_id)
    ) THEN
        RAISE EXCEPTION 'invalid Email XLSX extraction approval basis';
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER email_xlsx_extraction_approval_basis
    BEFORE INSERT ON public.brain_email_xlsx_extraction_approvals
    FOR EACH ROW EXECUTE FUNCTION public.guard_email_xlsx_extraction_approval();

ALTER TABLE public.brain_email_xlsx_extraction_approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.brain_email_xlsx_extraction_approvals FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON public.brain_email_xlsx_extraction_approvals USING
    (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid)
    WITH CHECK (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid);
CREATE POLICY tenant_login_fence ON public.brain_email_xlsx_extraction_approvals
    AS RESTRICTIVE FOR ALL TO PUBLIC
    USING (public.masterbrain_tenant_login_allows(tenant_id))
    WITH CHECK (public.masterbrain_tenant_login_allows(tenant_id));
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE
    ON public.brain_email_xlsx_extraction_approvals
    FOR EACH ROW EXECUTE FUNCTION public.deny_evidence_mutation();
CREATE TRIGGER protected_no_truncate BEFORE TRUNCATE
    ON public.brain_email_xlsx_extraction_approvals
    FOR EACH STATEMENT EXECUTE FUNCTION public.deny_protected_truncate();

COMMIT;
