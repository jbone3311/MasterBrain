BEGIN;

-- New run items precede their receipt in the same transaction. The deferred
-- receipt trigger validates the final ledger once, and this FK still refuses
-- an orphan when the transaction commits.
ALTER TABLE public.brain_fileos_run_items
    ALTER CONSTRAINT brain_fileos_run_items_tenant_id_actor_id_run_id_source_id_fkey
    DEFERRABLE INITIALLY DEFERRED;

DROP TRIGGER fileos_run_item_ledger ON public.brain_fileos_run_items;

CREATE FUNCTION public.lock_fileos_run_receipt_source() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
BEGIN
    -- Direct SQL receipt writers must serialize with item writers too; relying
    -- only on the application lock would leave an uncommitted-receipt race.
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
        NEW.tenant_id::text || ':fileos-source:' || NEW.source_id,0));
    RETURN NEW;
END
$function$;

CREATE TRIGGER fileos_lock_run_receipt_source
    BEFORE INSERT ON public.brain_fileos_run_receipts FOR EACH ROW
    EXECUTE FUNCTION public.lock_fileos_run_receipt_source();

CREATE FUNCTION public.refuse_late_fileos_run_item() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
BEGIN
    -- This is the same source lock used by the private completion writer.
    -- Without it, a concurrent row could see no uncommitted receipt and
    -- commit after that receipt's deferred ledger check.
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
        NEW.tenant_id::text || ':fileos-source:' || NEW.source_id,0));
    IF EXISTS (
        SELECT 1 FROM public.brain_fileos_run_receipts
        WHERE tenant_id=NEW.tenant_id AND actor_id=NEW.actor_id AND run_id=NEW.run_id
    ) THEN
        RAISE EXCEPTION 'sealed FileOS run item ledger';
    END IF;
    RETURN NEW;
END
$function$;

CREATE TRIGGER fileos_no_late_run_item
    BEFORE INSERT ON public.brain_fileos_run_items FOR EACH ROW
    EXECUTE FUNCTION public.refuse_late_fileos_run_item();

COMMIT;
