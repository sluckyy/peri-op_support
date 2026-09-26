-- Deterministic core schema, translated from the Full Project
-- Specification v1.0, Table 28 (Machine-readable schemas / relational
-- schema reference), plus the two additions from
-- docs/addenda/v1.1-gap-remediation.md (marked ADDENDUM below).
--
-- Cross-object invariants (Table 20) are NOT fully expressible in SQL
-- alone (the spec says as much in §12.3) and remain service-level
-- controls in periop_core.models / periop_core.services. The CHECK
-- constraints below cover only what SQL can enforce cheaply.

CREATE EXTENSION IF NOT EXISTS pgcrypto; -- for gen_random_uuid()

CREATE TYPE session_status AS ENUM (
    'INITIALISE', 'ACTIVE', 'PAUSED', 'COMPLETE', 'HANDOFF', 'STOPPED'
);

-- ADDENDUM (gap #2, INV-018): intake eligibility result.
CREATE TYPE eligibility_result AS ENUM ('ELIGIBLE', 'INELIGIBLE');

CREATE TYPE assertion_state AS ENUM (
    'AFFIRMED', 'NEGATED', 'UNCERTAIN', 'UNKNOWN', 'DECLINED', 'CONDITIONAL'
);

CREATE TYPE certainty AS ENUM (
    'EXPLICIT', 'INFERRED_LOW', 'INFERRED_MODERATE', 'UNRESOLVED'
);

CREATE TYPE verification_state AS ENUM (
    'CONFIRMED', 'UNCONFIRMED', 'CONFLICTED', 'STALE', 'UNKNOWN'
);

CREATE TYPE fact_assertion_role AS ENUM ('SUPPORTS', 'DISSENTS', 'SUPERSEDES');

CREATE TYPE conflict_type AS ENUM (
    'VALUE', 'NEGATION', 'TEMPORAL', 'IDENTITY', 'TERMINOLOGY', 'SOURCE', 'PROCEDURE'
);

CREATE TYPE materiality AS ENUM ('LOW', 'MODERATE', 'HIGH', 'CRITICAL');

CREATE TYPE conflict_status AS ENUM ('OPEN', 'RESOLVED', 'ACCEPTED_RISK');

-- The 12-state information taxonomy, Table 5.
CREATE TYPE information_state AS ENUM (
    'KNOWN_CONFIRMED', 'KNOWN_UNCONFIRMED', 'PARTIAL', 'STALE', 'CONFLICTING',
    'UNKNOWN', 'NOT_ASKED', 'DECLINED', 'NOT_APPLICABLE', 'UNAVAILABLE',
    'DEFERRED', 'SAFETY_ESCALATED'
);

CREATE TYPE gap_type AS ENUM (
    'MISSING', 'PARTIAL', 'STALE', 'UNVERIFIED', 'CONFLICTING',
    'UNAVAILABLE_SOURCE', 'DEFERRED', 'SAFETY_ESCALATED'
);

CREATE TYPE gap_status AS ENUM ('OPEN', 'RESOLVED', 'DEFERRED', 'HANDOFF');

-- The full InterviewAction vocabulary, Table 7.
CREATE TYPE action_type AS ENUM (
    'OPEN_INVITATION', 'FACILITATE', 'REFLECT', 'SUMMARISE', 'AGENDA_SOLICIT',
    'SIGNPOST', 'FOCUSED_PROBE', 'CLOSED_SCREEN', 'CONFIRM', 'CLARIFY',
    'EXPLAIN_REASON', 'REQUEST_SOURCE', 'CREATE_TASK', 'INTERRUPT_FOR_SAFETY',
    'HANDOFF', 'RETURN_TO_TOPIC', 'FINAL_OPEN', 'TEACH_BACK'
);

CREATE TYPE interview_action_status AS ENUM ('SELECTED', 'DELIVERED', 'CANCELLED');

CREATE TYPE speaker AS ENUM ('PATIENT', 'AGENT', 'CLINICIAN', 'PROXY', 'SYSTEM');

CREATE TYPE modality AS ENUM ('TEXT', 'VOICE', 'ASSISTED');

CREATE TYPE task_type AS ENUM (
    'RETRIEVAL', 'CLINICAL_REVIEW', 'SAFETY', 'IDENTITY', 'PROCEDURE', 'OTHER'
);

CREATE TYPE task_priority AS ENUM ('ROUTINE', 'URGENT', 'CRITICAL');

CREATE TYPE task_status AS ENUM ('OPEN', 'ACKNOWLEDGED', 'RESOLVED', 'CANCELLED');

CREATE TYPE cue_type AS ENUM ('CLINICAL', 'EMOTIONAL', 'COMMUNICATION', 'SAFETY');

CREATE TYPE salience AS ENUM ('LOW', 'MODERATE', 'HIGH', 'CRITICAL');

CREATE TYPE cue_status AS ENUM ('OPEN', 'ADDRESSED', 'ESCALATED');

CREATE TYPE agenda_priority AS ENUM ('LOW', 'MODERATE', 'HIGH');

CREATE TYPE agenda_status AS ENUM ('OPEN', 'ADDRESSED', 'DEFERRED', 'HANDOFF');

CREATE TABLE release_manifest (
    manifest_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    manifest_json JSONB NOT NULL, -- all version IDs + hashes, per §12.2
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE session (
    session_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_ref  TEXT NOT NULL,
    encounter_ref TEXT,
    procedure_context_json JSONB NOT NULL DEFAULT '{}',
    status       session_status NOT NULL DEFAULT 'INITIALISE',
    manifest_id  UUID NOT NULL REFERENCES release_manifest (manifest_id),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- ADDENDUM (gap #1, INV-017): AI-role/data-use notice acknowledgement.
    notice_acknowledged_at TIMESTAMPTZ,
    -- ADDENDUM (gap #2, INV-018): intake eligibility result.
    eligibility_result eligibility_result
);
CREATE INDEX idx_session_subject_ref ON session (subject_ref);
CREATE INDEX idx_session_encounter_ref ON session (encounter_ref);
CREATE INDEX idx_session_status ON session (status);
CREATE INDEX idx_session_created_at ON session (created_at);

CREATE TABLE assertion (
    assertion_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id   UUID NOT NULL REFERENCES session (session_id),
    subject_ref  TEXT NOT NULL,
    concept_json JSONB NOT NULL, -- code/display/system + mapping state (TERM-001..013)
    value_json   JSONB,
    assertion_state assertion_state NOT NULL,
    source_json  JSONB NOT NULL, -- type/ref/speaker/document/turn (INV-001)
    event_time_json JSONB,
    assertion_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    certainty    certainty NOT NULL,
    provenance_json JSONB NOT NULL, -- INV-001: never empty (enforced in app layer too)
    supersedes_assertion_id UUID REFERENCES assertion (assertion_id),
    CONSTRAINT assertion_provenance_not_empty CHECK (provenance_json <> '{}'::jsonb),
    CONSTRAINT assertion_not_self_superseding CHECK (supersedes_assertion_id <> assertion_id)
);
CREATE INDEX idx_assertion_session_id ON assertion (session_id);
CREATE INDEX idx_assertion_subject_ref ON assertion (subject_ref);

CREATE TABLE working_fact (
    fact_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id   UUID NOT NULL REFERENCES session (session_id),
    concept_json JSONB NOT NULL,
    value_json   JSONB,
    verification_state verification_state NOT NULL,
    freshness_json JSONB,
    version      INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX idx_working_fact_session_id ON working_fact (session_id);

-- INV-003 (WorkingFact cannot exist without a supporting assertion) is
-- enforced in the application layer (periop_core.models.WorkingFact),
-- not by a DB constraint, because a working_fact row and its first
-- fact_assertion_link row cannot both be inserted atomically as a single
-- CHECK without a deferred trigger; a trigger is a reasonable follow-up
-- if this schema is used directly (rather than only through the service
-- layer, which is the intended access path -- see INV-013).
CREATE TABLE fact_assertion_link (
    fact_id      UUID NOT NULL REFERENCES working_fact (fact_id),
    assertion_id UUID NOT NULL REFERENCES assertion (assertion_id),
    role         fact_assertion_role NOT NULL,
    PRIMARY KEY (fact_id, assertion_id)
);

CREATE TABLE conflict (
    conflict_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id   UUID NOT NULL REFERENCES session (session_id),
    type         conflict_type NOT NULL,
    materiality  materiality NOT NULL,
    status       conflict_status NOT NULL DEFAULT 'OPEN',
    resolution_json JSONB
);
CREATE INDEX idx_conflict_session_id ON conflict (session_id);
CREATE INDEX idx_conflict_materiality ON conflict (materiality);
CREATE INDEX idx_conflict_status ON conflict (status);

CREATE TABLE conflict_assertion_link (
    conflict_id  UUID NOT NULL REFERENCES conflict (conflict_id),
    assertion_id UUID NOT NULL REFERENCES assertion (assertion_id),
    PRIMARY KEY (conflict_id, assertion_id)
);

CREATE TABLE requirement_state (
    requirement_state_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id   UUID NOT NULL REFERENCES session (session_id),
    requirement_id TEXT NOT NULL, -- versioned Clinical Dataset Concept_ID
    information_state information_state NOT NULL,
    evidence_refs_json JSONB,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_requirement_state_session_id ON requirement_state (session_id);
CREATE INDEX idx_requirement_state_requirement_id ON requirement_state (requirement_id);
CREATE INDEX idx_requirement_state_information_state ON requirement_state (information_state);

CREATE TABLE information_gap (
    gap_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    requirement_state_id UUID NOT NULL REFERENCES requirement_state (requirement_state_id),
    gap_type     gap_type NOT NULL,
    priority_score DECIMAL NOT NULL,
    status       gap_status NOT NULL DEFAULT 'OPEN',
    resolution_options_json JSONB NOT NULL DEFAULT '[]'
);
CREATE INDEX idx_information_gap_requirement_state_id ON information_gap (requirement_state_id);
CREATE INDEX idx_information_gap_priority_score ON information_gap (priority_score);
CREATE INDEX idx_information_gap_status ON information_gap (status);

CREATE TABLE interview_action (
    action_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id   UUID NOT NULL REFERENCES session (session_id),
    action_type  action_type NOT NULL,
    contract_json JSONB NOT NULL, -- targets, permitted/prohibited content, max_questions
    status       interview_action_status NOT NULL DEFAULT 'SELECTED'
);
CREATE INDEX idx_interview_action_session_id ON interview_action (session_id);

CREATE TABLE turn (
    turn_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id   UUID NOT NULL REFERENCES session (session_id),
    action_id    UUID REFERENCES interview_action (action_id),
    speaker      speaker NOT NULL,
    modality     modality NOT NULL,
    content      TEXT NOT NULL,
    confidence   DECIMAL,
    occurred_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_turn_session_id ON turn (session_id);
CREATE INDEX idx_turn_occurred_at ON turn (occurred_at);

CREATE TABLE task (
    task_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id   UUID NOT NULL REFERENCES session (session_id),
    type         task_type NOT NULL,
    owner_ref    TEXT,
    priority     task_priority NOT NULL,
    status       task_status NOT NULL DEFAULT 'OPEN',
    reason_json  JSONB NOT NULL
);
CREATE INDEX idx_task_session_id ON task (session_id);
CREATE INDEX idx_task_owner_ref ON task (owner_ref);
CREATE INDEX idx_task_priority ON task (priority);
CREATE INDEX idx_task_status ON task (status);

CREATE TABLE cue (
    cue_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id   UUID NOT NULL REFERENCES session (session_id),
    turn_id      UUID NOT NULL REFERENCES turn (turn_id),
    cue_type     cue_type NOT NULL,
    salience     salience NOT NULL,
    status       cue_status NOT NULL DEFAULT 'OPEN'
);
CREATE INDEX idx_cue_session_id ON cue (session_id);

CREATE TABLE patient_agenda_item (
    agenda_item_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id   UUID NOT NULL REFERENCES session (session_id),
    text         TEXT NOT NULL,
    priority     agenda_priority NOT NULL,
    status       agenda_status NOT NULL DEFAULT 'OPEN',
    source_turn_id UUID REFERENCES turn (turn_id)
);
CREATE INDEX idx_patient_agenda_item_session_id ON patient_agenda_item (session_id);
