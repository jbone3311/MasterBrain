BEGIN;

-- ADR-266: an approved fact-proposal decision must name the fact published
-- from exactly that proposal, by the deciding reviewer, and an imported claim
-- may be approved once. Artifact decisions already bind content (0070); they
-- gain the same reviewer and single-approval rules. Existing rows are not
-- rewritten; these guards apply to new decisions.
CREATE OR REPLACE FUNCTION public.guard_fact_proposal_decision() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
BEGIN
    IF NEW.reviewer_id<>nullif(current_setting('email_brain.actor_id',true),'')::uuid THEN
        RAISE EXCEPTION 'fact proposal reviewer must be the current actor';
    END IF;
    IF NEW.decision='approved' AND NOT EXISTS (
        SELECT 1 FROM public.knowledge_project_fact_receipts r
        JOIN public.knowledge_project_facts f
          ON f.tenant_id=r.tenant_id AND f.id=r.fact_id
        JOIN public.knowledge_fact_proposals p
          ON p.tenant_id=NEW.tenant_id AND p.id=NEW.proposal_id
        WHERE r.tenant_id=NEW.tenant_id AND r.actor_id=NEW.reviewer_id
          AND r.idempotency_key=NEW.publication_key AND r.fact_id=NEW.fact_id
          AND p.batch_id=NEW.batch_id AND f.reviewer_id=NEW.reviewer_id
          AND f.project_id=p.payload->>'project_id'
          AND f.predicate=p.payload->>'predicate'
          AND f.value=p.payload->>'value'
          AND f.value_type=p.payload->>'value_type'
          AND f.assertion_status=p.payload->>'assertion_status'
          AND f.derivation=p.payload->>'derivation'
          AND f.confidence=(p.payload->>'confidence')::double precision
          AND f.quote_evidence_id=p.quote_evidence_id
          AND f.source_quote=p.payload->>'source_quote'
          AND f.observed_at=(p.payload->>'observed_at')::timestamptz
          AND f.supersedes_id IS NULL AND f.valid_from IS NULL AND f.valid_to IS NULL
          AND f.evidence_ids=ARRAY(
              SELECT e.id FROM jsonb_array_elements_text(p.payload->'evidence_ids')
                  WITH ORDINALITY AS e(id,n) ORDER BY e.n)
          AND f.amount_decimal IS NOT DISTINCT FROM
              (p.payload->'measurement'->>'amount')::numeric
          AND f.unit_code IS NOT DISTINCT FROM p.payload->'measurement'->>'unit'
          AND f.currency_code IS NOT DISTINCT FROM p.payload->'measurement'->>'currency'
    ) THEN
        RAISE EXCEPTION 'invalid fact proposal approval receipt';
    END IF;
    IF NEW.decision='approved' AND EXISTS (
        SELECT 1 FROM public.knowledge_fact_proposals mine
        JOIN public.knowledge_fact_proposals other
          ON other.tenant_id=mine.tenant_id AND other.claimed_id=mine.claimed_id
         AND other.id<>mine.id
        JOIN public.knowledge_fact_proposal_decisions d
          ON d.tenant_id=other.tenant_id AND d.proposal_id=other.id
        WHERE mine.tenant_id=NEW.tenant_id AND mine.id=NEW.proposal_id
          AND d.decision='approved'
    ) THEN
        RAISE EXCEPTION 'imported fact claim was already approved';
    END IF;
    RETURN NEW;
END
$function$;

CREATE FUNCTION public.guard_artifact_proposal_decision_reviewer() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
BEGIN
    IF NEW.reviewer_id<>nullif(current_setting('email_brain.actor_id',true),'')::uuid THEN
        RAISE EXCEPTION 'artifact proposal reviewer must be the current actor';
    END IF;
    IF NEW.decision='approved' AND EXISTS (
        SELECT 1 FROM public.knowledge_artifact_proposals mine
        JOIN public.knowledge_artifact_proposals other
          ON other.tenant_id=mine.tenant_id AND other.claimed_id=mine.claimed_id
         AND other.id<>mine.id
        JOIN public.knowledge_artifact_proposal_decisions d
          ON d.tenant_id=other.tenant_id AND d.proposal_id=other.id
        WHERE mine.tenant_id=NEW.tenant_id AND mine.id=NEW.proposal_id
          AND d.decision='approved'
    ) THEN
        RAISE EXCEPTION 'imported artifact claim was already approved';
    END IF;
    RETURN NEW;
END
$function$;
CREATE TRIGGER artifact_proposal_decision_reviewer
    BEFORE INSERT ON public.knowledge_artifact_proposal_decisions
    FOR EACH ROW EXECUTE FUNCTION public.guard_artifact_proposal_decision_reviewer();

COMMIT;
