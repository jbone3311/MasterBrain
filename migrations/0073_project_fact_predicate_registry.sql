BEGIN;

-- ADR-214: a versioned, migration-controlled global vocabulary for NEW
-- reviewed project facts. Historical rows keep NULL and their original text.
CREATE TABLE public.knowledge_project_fact_predicates (
    name text NOT NULL CHECK (name ~ '^[a-z][a-z0-9_.-]{0,99}$'),
    version integer NOT NULL CHECK (version>0),
    value_type text NOT NULL CHECK (value_type IN
        ('text','number','date','boolean','reference')),
    unit_code text CHECK (unit_code IN ('currency','shares','percent','count')),
    description text NOT NULL CHECK (length(description) BETWEEN 1 AND 300),
    status text NOT NULL CHECK (status IN ('active','deprecated')),
    PRIMARY KEY (name,version),
    CHECK ((value_type='number' AND unit_code IS NOT NULL)
        OR (value_type<>'number' AND unit_code IS NULL))
);
INSERT INTO public.knowledge_project_fact_predicates
    (name,version,value_type,unit_code,description,status) VALUES
    ('deal.note',1,'text',NULL,'Source-stated project note; not a summary.','active'),
    ('loan.proposed_amount',1,'text',NULL,
     'Raw proposed loan amount before canonical numeric extraction.','active'),
    ('capital.amount',1,'number','currency',
     'Source-stated capital amount; not a balance.','active'),
    ('loi.price',1,'number','currency',
     'Source-stated letter-of-intent price; not a sale.','active'),
    ('capital_call.amount',1,'number','currency',
     'Source-stated capital-call amount; not paid capital.','active');

CREATE TRIGGER immutable BEFORE UPDATE OR DELETE
    ON public.knowledge_project_fact_predicates
    FOR EACH ROW EXECUTE FUNCTION public.deny_evidence_mutation();
CREATE TRIGGER protected_no_truncate BEFORE TRUNCATE
    ON public.knowledge_project_fact_predicates
    FOR EACH STATEMENT EXECUTE FUNCTION public.deny_protected_truncate();

ALTER TABLE public.knowledge_project_facts
    ADD COLUMN predicate_registry_version integer;

CREATE FUNCTION public.guard_project_fact_predicate() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
DECLARE spec record;
BEGIN
    SELECT p.version,p.value_type,p.unit_code INTO spec
    FROM public.knowledge_project_fact_predicates AS p
    WHERE p.name=NEW.predicate AND p.status='active'
    ORDER BY p.version DESC LIMIT 1;
    IF NOT FOUND OR NEW.value_type<>spec.value_type
       OR NEW.unit_code IS DISTINCT FROM spec.unit_code
       OR (NEW.predicate_registry_version IS NOT NULL
           AND NEW.predicate_registry_version<>spec.version) THEN
        RAISE EXCEPTION 'project fact predicate is not an active registered shape';
    END IF;
    NEW.predicate_registry_version := spec.version;
    RETURN NEW;
END
$function$;
CREATE TRIGGER registered_project_fact_guard
    BEFORE INSERT ON public.knowledge_project_facts
    FOR EACH ROW EXECUTE FUNCTION public.guard_project_fact_predicate();

COMMIT;
