BEGIN;

-- The semantic transform revision is a server property, not a value supplied
-- by the human reviewer. Preserve earlier rows, but reject new false claims.
CREATE FUNCTION public.guard_email_xlsx_bridge_revision() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
BEGIN
    IF NEW.code_revision <> 'email-xlsx-document-bridge-v2' THEN
        RAISE EXCEPTION 'invalid Email XLSX bridge revision';
    END IF;
    RETURN NEW;
END
$function$;

CREATE TRIGGER email_xlsx_review_revision
    BEFORE INSERT ON public.brain_email_xlsx_publication_reviews
    FOR EACH ROW EXECUTE FUNCTION public.guard_email_xlsx_bridge_revision();

CREATE TRIGGER email_xlsx_receipt_revision
    BEFORE INSERT ON public.brain_email_xlsx_document_bridge_receipts
    FOR EACH ROW EXECUTE FUNCTION public.guard_email_xlsx_bridge_revision();

COMMIT;
