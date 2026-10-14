BEGIN;

CREATE INDEX brain_email_bridge_evidence_exclusion_lookup
    ON public.brain_email_bridge_receipts(tenant_id,evidence_id);
CREATE INDEX brain_email_attachment_evidence_exclusion_lookup
    ON public.brain_email_attachment_bridge_receipts(tenant_id,evidence_id);
CREATE INDEX brain_email_document_evidence_exclusion_lookup
    ON public.brain_email_document_bridge_receipts(tenant_id,evidence_id);

-- SECURITY INVOKER is deliberate: every underlying table keeps its forced
-- tenant RLS and the caller needs its existing SELECT grants. No source bytes,
-- mailbox IDs or provider IDs are returned by this predicate.
CREATE FUNCTION public.brain_email_evidence_is_excluded(
    target_tenant uuid, target_evidence text
) RETURNS boolean
LANGUAGE sql STABLE SECURITY INVOKER
SET search_path = pg_catalog, public
AS $body$
    SELECT EXISTS (
        SELECT 1 FROM (
            SELECT b.tenant_id,b.account_id,b.legacy_version_id
            FROM public.brain_email_bridge_receipts b
            WHERE b.tenant_id=target_tenant AND b.evidence_id=target_evidence
            UNION ALL
            SELECT b.tenant_id,b.account_id,b.legacy_parent_version_id
            FROM public.brain_email_attachment_bridge_receipts b
            WHERE b.tenant_id=target_tenant AND b.evidence_id=target_evidence
            UNION ALL
            SELECT b.tenant_id,b.account_id,a.evidence_id AS legacy_version_id
            FROM public.brain_email_document_bridge_receipts b
            JOIN public.attachment_receipts a
              ON a.tenant_id=b.tenant_id AND a.account_id=b.account_id
             AND a.id=b.legacy_attachment_id
            WHERE b.tenant_id=target_tenant AND b.evidence_id=target_evidence
        ) link
        JOIN public.message_versions v
          ON v.tenant_id=link.tenant_id AND v.account_id=link.account_id
         AND v.id=link.legacy_version_id
        JOIN public.messages m
          ON m.tenant_id=v.tenant_id AND m.account_id=v.account_id
         AND m.id=v.message_id
        JOIN public.message_sync_state s
          ON s.tenant_id=m.tenant_id AND s.account_id=m.account_id
         AND s.provider_id=m.provider_message_id
        WHERE s.status='excluded'
    );
$body$;

COMMIT;
