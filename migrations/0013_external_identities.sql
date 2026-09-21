BEGIN;

-- Authority is administrator-managed, never populated from incoming token claims.
CREATE TABLE external_identities (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    actor_id uuid NOT NULL,
    issuer text NOT NULL CHECK (octet_length(issuer) BETWEEN 1 AND 1024),
    subject text NOT NULL CHECK (octet_length(subject) BETWEEN 1 AND 512),
    client_id text NOT NULL CHECK (octet_length(client_id) BETWEEN 1 AND 512),
    scopes text[] NOT NULL CHECK (
        cardinality(scopes) BETWEEN 1 AND 5
        AND array_ndims(scopes) = 1
        AND array_position(scopes, NULL) IS NULL
        AND scopes <@ ARRAY['email.search','email.evidence.read','email.proposal.create',
                            'email.proposal.read','email.review']::text[]
    ),
    client_kind text NOT NULL CHECK (client_kind IN ('human','assistant')),
    active boolean NOT NULL DEFAULT true,
    revision bigint NOT NULL DEFAULT 1 CHECK (revision > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (issuer,subject,client_id),
    FOREIGN KEY (tenant_id,actor_id) REFERENCES tenant_memberships(tenant_id,user_id),
    CHECK (client_kind = 'human' OR NOT ('email.review' = ANY(scopes)))
);

CREATE FUNCTION protect_external_identity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.revision <> 1 THEN
            RAISE EXCEPTION 'initial identity revision must be one';
        END IF;
    ELSE
        IF ROW(NEW.id,NEW.tenant_id,NEW.actor_id,NEW.issuer,NEW.subject,NEW.client_id,NEW.created_at)
           IS DISTINCT FROM
           ROW(OLD.id,OLD.tenant_id,OLD.actor_id,OLD.issuer,OLD.subject,OLD.client_id,OLD.created_at)
           OR NEW.revision <> OLD.revision THEN
            RAISE EXCEPTION 'identity binding is immutable';
        END IF;
        NEW.revision := OLD.revision + 1;
        NEW.updated_at := clock_timestamp();
    END IF;
    IF cardinality(NEW.scopes) <> (SELECT count(DISTINCT s) FROM unnest(NEW.scopes) AS s) THEN
        RAISE EXCEPTION 'duplicate identity scopes';
    END IF;
    RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION protect_external_identity() FROM PUBLIC;
CREATE TRIGGER external_identity_protection BEFORE INSERT OR UPDATE ON external_identities
FOR EACH ROW EXECUTE FUNCTION protect_external_identity();

CREATE FUNCTION audit_external_identity() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE entry external_identities%ROWTYPE;
BEGIN
    IF TG_OP = 'DELETE' THEN entry := OLD; ELSE entry := NEW; END IF;
    INSERT INTO audit_events(tenant_id,actor_id,request_id,event_type,resource_type,
                             resource_id,outcome,metadata)
    VALUES (entry.tenant_id,NULL,gen_random_uuid(),'identity.' || lower(TG_OP),
            'external_identity',entry.id::text,'ok',
            jsonb_build_object('database_role',current_user,'revision',entry.revision,
                               'active',entry.active,'scopes',entry.scopes,
                               'client_kind',entry.client_kind));
    RETURN NULL;
END;
$$;
REVOKE ALL ON FUNCTION audit_external_identity() FROM PUBLIC;
CREATE TRIGGER external_identity_audit AFTER INSERT OR UPDATE OR DELETE ON external_identities
FOR EACH ROW EXECUTE FUNCTION audit_external_identity();

ALTER TABLE external_identities ENABLE ROW LEVEL SECURITY;
ALTER TABLE external_identities FORCE ROW LEVEL SECURITY;
CREATE POLICY verified_identity_lookup ON external_identities FOR SELECT USING (
    issuer = nullif(current_setting('email_brain.auth_issuer', true), '')
    AND subject = nullif(current_setting('email_brain.auth_subject', true), '')
    AND client_id = nullif(current_setting('email_brain.auth_client', true), '')
);

COMMIT;
