BEGIN;

-- ADR-177. Administrator-owned account pin; runtime has no mail_accounts UPDATE.
ALTER TABLE public.mail_accounts ADD COLUMN read_scope_sha256 text
    CHECK (read_scope_sha256 IS NULL OR read_scope_sha256 ~ '^[0-9a-f]{64}$');
ALTER TABLE public.sync_workers ADD COLUMN read_scope_sha256 text
    CHECK (read_scope_sha256 IS NULL OR read_scope_sha256 ~ '^[0-9a-f]{64}$');
ALTER TABLE public.sync_workers ADD COLUMN scope_claim_token uuid;

CREATE FUNCTION public.guard_fastmail_scope_enrollment() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
BEGIN
    IF NEW.read_scope_sha256 IS NOT DISTINCT FROM OLD.read_scope_sha256 THEN
        RETURN NEW;
    END IF;
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
        OLD.tenant_id::text || ':' || OLD.id::text, 0));
    IF NEW.provider <> 'fastmail' OR EXISTS (
        SELECT 1 FROM public.sync_workers WHERE tenant_id=OLD.tenant_id AND account_id=OLD.id
    ) OR EXISTS (
        SELECT 1 FROM public.sync_cursors WHERE tenant_id=OLD.tenant_id AND account_id=OLD.id
    ) OR EXISTS (
        SELECT 1 FROM public.provider_events WHERE tenant_id=OLD.tenant_id AND account_id=OLD.id
    ) OR EXISTS (
        SELECT 1 FROM public.message_sync_state WHERE tenant_id=OLD.tenant_id AND account_id=OLD.id
    ) OR EXISTS (
        SELECT 1 FROM public.raw_objects WHERE tenant_id=OLD.tenant_id AND account_id=OLD.id
    ) OR EXISTS (
        SELECT 1 FROM public.messages WHERE tenant_id=OLD.tenant_id AND account_id=OLD.id
    ) THEN
        RAISE EXCEPTION 'mail scope cannot change after account use';
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER fastmail_scope_enrollment BEFORE UPDATE OF read_scope_sha256
    ON public.mail_accounts FOR EACH ROW
    EXECUTE FUNCTION public.guard_fastmail_scope_enrollment();

CREATE FUNCTION public.guard_fastmail_scope_lease() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
DECLARE expected text;
BEGIN
    SELECT a.read_scope_sha256 INTO expected FROM public.mail_accounts AS a
    WHERE a.tenant_id=NEW.tenant_id AND a.id=NEW.account_id;
    IF expected IS NULL THEN
        IF NEW.read_scope_sha256 IS NOT NULL OR NEW.scope_claim_token IS NOT NULL THEN
            RAISE EXCEPTION 'unexpected scoped worker claim';
        END IF;
    ELSIF NEW.read_scope_sha256 IS DISTINCT FROM expected
       OR NEW.scope_claim_token IS DISTINCT FROM NEW.lease_token THEN
        RAISE EXCEPTION 'scoped worker claim does not match account and lease';
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER fastmail_scope_lease BEFORE INSERT OR UPDATE ON public.sync_workers
    FOR EACH ROW EXECUTE FUNCTION public.guard_fastmail_scope_lease();

CREATE FUNCTION public.guard_fastmail_scope_cursor() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
DECLARE expected text;
DECLARE checkpoint jsonb;
BEGIN
    IF NEW.scope <> 'email' THEN
        RETURN NEW;
    END IF;
    SELECT a.read_scope_sha256 INTO expected FROM public.mail_accounts AS a
    WHERE a.tenant_id=NEW.tenant_id AND a.id=NEW.account_id;
    IF expected IS NOT NULL OR pg_catalog.left(pg_catalog.ltrim(NEW.opaque_cursor),1)='{' THEN
        checkpoint := NEW.opaque_cursor::jsonb;
        IF expected IS NULL THEN
            IF checkpoint->>'schema_version'='4' THEN
                RAISE EXCEPTION 'scoped cursor needs pinned account';
            END IF;
        ELSIF pg_catalog.jsonb_typeof(checkpoint)<>'object'
           OR checkpoint->>'schema_version'<>'4'
           OR checkpoint->>'scope_sha256' IS DISTINCT FROM expected THEN
            RAISE EXCEPTION 'scoped cursor does not match pinned account';
        END IF;
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER fastmail_scope_cursor BEFORE INSERT OR UPDATE ON public.sync_cursors
    FOR EACH ROW EXECUTE FUNCTION public.guard_fastmail_scope_cursor();

COMMIT;
