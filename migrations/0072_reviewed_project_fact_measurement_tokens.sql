BEGIN;

-- ADR-213: harden migration 0071's substring checks for new and existing
-- typed rows. A migration fails closed if an already-published typed row only
-- matched a fragment; no reviewed fact is silently rewritten or discarded.
ALTER TABLE public.knowledge_project_facts
    DROP CONSTRAINT knowledge_project_fact_measurement_shape;

ALTER TABLE public.knowledge_project_facts
    ADD CONSTRAINT knowledge_project_fact_measurement_shape CHECK (
        (amount_decimal IS NULL AND unit_code IS NULL AND currency_code IS NULL)
        OR (amount_decimal IS NOT NULL AND value_type='number'
            AND unit_code IS NOT NULL
            AND unit_code IN ('currency','shares','percent','count')
            AND ((unit_code='currency' AND currency_code IS NOT NULL
                  AND currency_code ~ '^[A-Z]{3}$')
                 OR (unit_code<>'currency' AND currency_code IS NULL))
            AND source_quote ~ (
                '(^|[^[:alnum:]_.-])' || replace(value,'.','[.]')
                || '($|[^[:alnum:]_.])'
            )
            AND CASE WHEN unit_code='currency'
                THEN source_quote ~ (
                    '(^|[^[:alnum:]_])' || currency_code || '($|[^[:alnum:]_])'
                )
                ELSE source_quote ~ (
                    '(^|[^[:alnum:]_])' || unit_code || '($|[^[:alnum:]_])'
                ) END
            AND CASE WHEN value ~ '^-?(0|[1-9][0-9]{0,21})(\.[0-9]{1,8})?$'
                THEN value::numeric=amount_decimal ELSE false END)
    );

COMMIT;
