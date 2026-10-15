BEGIN;

-- ADR-215: a later deprecated revision must retire the name. Looking for
-- the latest *active* revision would silently revive an older active row.
CREATE OR REPLACE FUNCTION public.guard_project_fact_predicate() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
DECLARE spec record;
BEGIN
    SELECT p.version,p.status,p.value_type,p.unit_code INTO spec
    FROM public.knowledge_project_fact_predicates AS p
    WHERE p.name=NEW.predicate
    ORDER BY p.version DESC LIMIT 1;
    IF NOT FOUND OR spec.status<>'active'
       OR NEW.value_type<>spec.value_type
       OR NEW.unit_code IS DISTINCT FROM spec.unit_code
       OR (NEW.predicate_registry_version IS NOT NULL
           AND NEW.predicate_registry_version<>spec.version) THEN
        RAISE EXCEPTION 'project fact predicate is not an active registered shape';
    END IF;
    NEW.predicate_registry_version := spec.version;
    RETURN NEW;
END
$function$;

COMMIT;
