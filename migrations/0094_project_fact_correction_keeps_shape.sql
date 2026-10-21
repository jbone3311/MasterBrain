BEGIN;

-- ADR-265: the predicate registry gates new fact chains, not corrections. A
-- reviewed fact must stay correctable (SECURITY.md), and a successor must
-- keep its prior's project, predicate and type (0066). When the registry no
-- longer admits that shape (deprecated or never registered), a successor may
-- still keep the exact prior shape and its recorded registry version.
CREATE OR REPLACE FUNCTION public.guard_project_fact_predicate() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
DECLARE spec record;
DECLARE prior record;
BEGIN
    SELECT p.version,p.status,p.value_type,p.unit_code INTO spec
    FROM public.knowledge_project_fact_predicates AS p
    WHERE p.name=NEW.predicate
    ORDER BY p.version DESC LIMIT 1;
    IF FOUND AND spec.status='active'
       AND NEW.value_type=spec.value_type
       AND NEW.unit_code IS NOT DISTINCT FROM spec.unit_code
       AND (NEW.predicate_registry_version IS NULL
            OR NEW.predicate_registry_version=spec.version) THEN
        NEW.predicate_registry_version := spec.version;
        RETURN NEW;
    END IF;
    IF NEW.supersedes_id IS NOT NULL THEN
        SELECT f.project_id,f.predicate,f.value_type,f.unit_code,
               f.predicate_registry_version INTO prior
        FROM public.knowledge_project_facts AS f
        WHERE f.tenant_id=NEW.tenant_id AND f.id=NEW.supersedes_id;
        IF FOUND AND prior.project_id=NEW.project_id
           AND prior.predicate=NEW.predicate AND prior.value_type=NEW.value_type
           AND prior.unit_code IS NOT DISTINCT FROM NEW.unit_code
           AND (NEW.predicate_registry_version IS NULL
                OR NEW.predicate_registry_version
                   IS NOT DISTINCT FROM prior.predicate_registry_version) THEN
            NEW.predicate_registry_version := prior.predicate_registry_version;
            RETURN NEW;
        END IF;
    END IF;
    RAISE EXCEPTION 'project fact predicate is not an active registered shape';
END
$function$;

COMMIT;
