-- SVC-014 (Audit & Provenance Service): "Immutable lineage" via
-- appendEvent/getLineage, with the acceptance test "clinical mutation
-- fails if provenance unavailable" -- see periop_core.audit_db and the
-- periop_api endpoints that call append_event in the same transaction
-- as the mutation they record.
--
-- Scope for this first pass: Phase 1 core session/assertion lifecycle
-- events only (session created, notice acknowledged, activated, an
-- assertion added, session closed) -- see README "What's implemented"
-- for exactly which mutations are and aren't wired in yet.

CREATE TYPE audit_event_type AS ENUM (
    'SESSION_CREATED', 'NOTICE_ACKNOWLEDGED', 'SESSION_ACTIVATED',
    'ASSERTION_ADDED', 'SESSION_CLOSED'
);

CREATE TABLE audit_event (
    event_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id   UUID NOT NULL REFERENCES session (session_id),
    event_type   audit_event_type NOT NULL,
    entity_type  TEXT NOT NULL,
    entity_id    UUID,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_event_session_id ON audit_event (session_id, occurred_at);

-- "Immutable lineage" enforced at the DB layer, not just by convention --
-- see 0001_init.sql's comment on fact_assertion_link for why a trigger
-- (rather than a CHECK) is the right tool for this kind of invariant.
CREATE FUNCTION audit_event_immutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_event is append-only (SVC-014): % not permitted', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_event_no_update
    BEFORE UPDATE ON audit_event
    FOR EACH ROW EXECUTE FUNCTION audit_event_immutable();

CREATE TRIGGER audit_event_no_delete
    BEFORE DELETE ON audit_event
    FOR EACH ROW EXECUTE FUNCTION audit_event_immutable();
