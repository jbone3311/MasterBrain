BEGIN;

-- Existing sources and receipts have no trustworthy physical-root identity.
-- Preserve that unknown state; bind only new sources or empty legacy sources.
ALTER TABLE brain_sources ADD COLUMN root_binding_sha256 text;
ALTER TABLE brain_sources ADD CONSTRAINT brain_fileos_source_root_binding_new
    CHECK (root_binding_sha256 IS NULL OR root_binding_sha256 ~ '^[a-f0-9]{64}$');

CREATE FUNCTION protect_fileos_source_root_binding() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.kind = 'fileos' AND NEW.root_binding_sha256 IS NULL THEN
            RAISE EXCEPTION 'New FileOS source requires a root binding';
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.kind IS DISTINCT FROM NEW.kind THEN
        RAISE EXCEPTION 'Source kind is immutable';
    END IF;
    IF OLD.root_binding_sha256 IS NOT NULL
       AND NEW.root_binding_sha256 IS DISTINCT FROM OLD.root_binding_sha256 THEN
        RAISE EXCEPTION 'FileOS source root binding is immutable';
    END IF;
    IF OLD.kind = 'fileos' AND OLD.root_binding_sha256 IS NULL
       AND NEW.root_binding_sha256 IS NOT NULL
       AND (EXISTS (
           SELECT 1 FROM public.brain_source_items
           WHERE tenant_id=OLD.tenant_id AND source_id=OLD.id
       ) OR EXISTS (
           SELECT 1 FROM public.brain_fileos_run_receipts
           WHERE tenant_id=OLD.tenant_id AND source_id=OLD.id
       )) THEN
        RAISE EXCEPTION 'Legacy FileOS source root binding requires review';
    END IF;
    RETURN NEW;
END;
$function$;
CREATE TRIGGER protect_fileos_root_binding
    BEFORE INSERT OR UPDATE ON brain_sources
    FOR EACH ROW EXECUTE FUNCTION protect_fileos_source_root_binding();

ALTER TABLE brain_fileos_run_receipts ADD COLUMN root_binding_sha256 text;
ALTER TABLE brain_fileos_run_receipts ADD CONSTRAINT brain_fileos_receipt_root_binding_new
    CHECK (root_binding_sha256 IS NOT NULL
           AND root_binding_sha256 ~ '^[a-f0-9]{64}$') NOT VALID;

COMMIT;
