BEGIN;

-- ADR-212: opt-in exact-decimal unit/currency metadata on reviewed facts.
-- Existing rows stay untyped; no historical value is parsed or rewritten.
ALTER TABLE public.knowledge_project_facts
    ADD COLUMN amount_decimal numeric(30,8),
    ADD COLUMN unit_code text,
    ADD COLUMN currency_code text;

ALTER TABLE public.knowledge_project_facts
    ADD CONSTRAINT knowledge_project_fact_measurement_shape CHECK (
        (amount_decimal IS NULL AND unit_code IS NULL AND currency_code IS NULL)
        OR (amount_decimal IS NOT NULL AND value_type='number'
            AND unit_code IS NOT NULL
            AND unit_code IN ('currency','shares','percent','count')
            AND ((unit_code='currency' AND currency_code IS NOT NULL
                  AND currency_code ~ '^[A-Z]{3}$')
                 OR (unit_code<>'currency' AND currency_code IS NULL))
            AND position(value IN source_quote)>0
            AND CASE WHEN unit_code='currency'
                THEN position(currency_code IN source_quote)>0
                ELSE position(unit_code IN source_quote)>0 END
            AND CASE WHEN value ~ '^-?(0|[1-9][0-9]{0,21})(\.[0-9]{1,8})?$'
                THEN value::numeric=amount_decimal ELSE false END)
    );

COMMIT;
