BEGIN;

-- A human authorizes an exact private result. A worker, never the reviewer,
-- performs DataCore publication through the separate ADR-241 receipt.
CREATE TABLE public.brain_email_xlsx_publication_reviews (
    tenant_id uuid NOT NULL,
    id text NOT NULL CHECK (id ~ '^xrev_[a-f0-9]{32}$'),
    actor_id uuid NOT NULL,
    idempotency_key uuid NOT NULL,
    approval_id text NOT NULL,
    account_id uuid NOT NULL,
    text_sha256 text NOT NULL CHECK (text_sha256 ~ '^[a-f0-9]{64}$'),
    sheet_count integer NOT NULL CHECK (sheet_count BETWEEN 1 AND 20),
    cell_count integer NOT NULL CHECK (cell_count BETWEEN 1 AND 20000),
    code_revision text NOT NULL CHECK (length(code_revision) BETWEEN 1 AND 200),
    request_hash text NOT NULL CHECK (request_hash ~ '^[a-f0-9]{64}$'),
    created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
    expires_at timestamptz NOT NULL DEFAULT statement_timestamp()+interval '1 hour',
    PRIMARY KEY (tenant_id,id),
    UNIQUE (tenant_id,actor_id,idempotency_key),
    UNIQUE (tenant_id,approval_id),
    FOREIGN KEY (tenant_id,approval_id)
        REFERENCES public.brain_email_xlsx_extraction_results(tenant_id,approval_id),
    FOREIGN KEY (tenant_id,account_id) REFERENCES public.mail_accounts(tenant_id,id),
    CHECK (expires_at=created_at+interval '1 hour')
);

CREATE FUNCTION public.guard_email_xlsx_publication_review() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
BEGIN
    IF NEW.actor_id IS DISTINCT FROM
       nullif(current_setting('email_brain.actor_id',true),'')::uuid THEN
        RAISE EXCEPTION 'Email XLSX publication reviewer context mismatch';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM public.brain_email_xlsx_extraction_results r
        JOIN public.brain_email_xlsx_extraction_approvals ap
          ON ap.tenant_id=r.tenant_id AND ap.id=r.approval_id
        JOIN public.brain_email_attachment_bridge_receipts ab
          ON ab.tenant_id=ap.tenant_id AND ab.account_id=ap.account_id
         AND ab.legacy_attachment_id=ap.attachment_id
        JOIN public.tenant_memberships reviewer
          ON reviewer.tenant_id=ap.tenant_id AND reviewer.user_id=NEW.actor_id
         AND reviewer.role='owner'
        JOIN public.tenant_memberships approver
          ON approver.tenant_id=ap.tenant_id AND approver.user_id=ap.actor_id
         AND approver.role='owner'
        WHERE r.tenant_id=NEW.tenant_id AND r.approval_id=NEW.approval_id
          AND ap.account_id=NEW.account_id AND ap.expires_at>clock_timestamp()
          AND r.text_sha256=NEW.text_sha256
          AND r.sheet_count=NEW.sheet_count AND r.cell_count=NEW.cell_count
          AND public.brain_email_xlsx_basis_current(
              r.tenant_id,r.approval_id,ab.evidence_id)
    ) THEN
        RAISE EXCEPTION 'invalid Email XLSX publication review basis';
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER email_xlsx_publication_review_basis
    BEFORE INSERT ON public.brain_email_xlsx_publication_reviews
    FOR EACH ROW EXECUTE FUNCTION public.guard_email_xlsx_publication_review();

ALTER TABLE public.brain_email_xlsx_publication_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.brain_email_xlsx_publication_reviews FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON public.brain_email_xlsx_publication_reviews USING
    (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid)
    WITH CHECK (tenant_id=nullif(current_setting('email_brain.tenant_id',true),'')::uuid);
CREATE POLICY tenant_login_fence ON public.brain_email_xlsx_publication_reviews
    AS RESTRICTIVE FOR ALL TO PUBLIC
    USING (public.masterbrain_tenant_login_allows(tenant_id))
    WITH CHECK (public.masterbrain_tenant_login_allows(tenant_id));
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE
    ON public.brain_email_xlsx_publication_reviews
    FOR EACH ROW EXECUTE FUNCTION public.deny_evidence_mutation();
CREATE TRIGGER protected_no_truncate BEFORE TRUNCATE
    ON public.brain_email_xlsx_publication_reviews
    FOR EACH STATEMENT EXECUTE FUNCTION public.deny_protected_truncate();

-- Nullable for receipts already written by the pre-0085 synthetic branch;
-- every new insert must bind a current, human-authored review.
ALTER TABLE public.brain_email_xlsx_document_bridge_receipts ADD COLUMN review_id text;
ALTER TABLE public.brain_email_xlsx_document_bridge_receipts
    ADD FOREIGN KEY (tenant_id,review_id)
    REFERENCES public.brain_email_xlsx_publication_reviews(tenant_id,id);

CREATE OR REPLACE FUNCTION public.guard_email_xlsx_document_bridge() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
BEGIN
    IF NEW.actor_id IS DISTINCT FROM
       nullif(current_setting('email_brain.actor_id',true),'')::uuid THEN
        RAISE EXCEPTION 'Email XLSX bridge worker context mismatch';
    END IF;
    IF NEW.review_id IS NULL OR NOT EXISTS (
        SELECT 1 FROM public.brain_email_xlsx_publication_reviews q
        JOIN public.brain_email_xlsx_extraction_results r
          ON r.tenant_id=q.tenant_id AND r.approval_id=q.approval_id
        JOIN public.brain_email_xlsx_extraction_approvals ap
          ON ap.tenant_id=r.tenant_id AND ap.id=r.approval_id
        JOIN public.brain_email_attachment_bridge_receipts ab
          ON ab.tenant_id=r.tenant_id AND ab.account_id=r.account_id
         AND ab.legacy_attachment_id=r.attachment_id
        JOIN public.brain_normalized_documents d
          ON d.tenant_id=ab.tenant_id AND d.id=NEW.document_id
        JOIN public.tenant_memberships reviewer
          ON reviewer.tenant_id=q.tenant_id AND reviewer.user_id=q.actor_id
         AND reviewer.role='owner'
        JOIN public.tenant_memberships approver
          ON approver.tenant_id=ap.tenant_id AND approver.user_id=ap.actor_id
         AND approver.role='owner'
        JOIN public.tenant_memberships worker
          ON worker.tenant_id=q.tenant_id AND worker.user_id=NEW.actor_id
         AND worker.role='owner'
        WHERE q.tenant_id=NEW.tenant_id AND q.id=NEW.review_id
          AND q.approval_id=NEW.approval_id AND q.expires_at>clock_timestamp()
          AND ap.expires_at>clock_timestamp()
          AND q.account_id=NEW.account_id AND r.account_id=NEW.account_id
          AND r.attachment_id=NEW.attachment_id
          AND q.text_sha256=r.text_sha256 AND q.sheet_count=r.sheet_count
          AND q.cell_count=r.cell_count AND q.code_revision=NEW.code_revision
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

COMMIT;
