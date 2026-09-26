-- v1.1 Model Layer tables (Full Spec §6A / Table 9), translated from
-- periop_core.model_layer. Reuses the `materiality` and `salience` enum
-- types already created in 0001_init.sql.
--
-- These objects are conversation-layer state, not clinical truth --
-- see periop_core/model_layer.py's module docstring for how e.g.
-- Contradiction relates to (but is not the same as) `conflict`, and
-- ProspectiveObligation relates to (but is not the same as) `task`.

CREATE TYPE epistemic_level AS ENUM (
    'L0_RAW_UTTERANCE', 'L1_LITERAL_INTERPRETATION', 'L2_PRAGMATIC_INTERPRETATION',
    'L3_CLINICAL_HYPOTHESIS', 'L4_PATIENT_GROUNDED', 'L5_EXTERNALLY_VERIFIED',
    'L6_CLINICALLY_ADJUDICATED'
);

CREATE TYPE hypothesis_status AS ENUM ('ACTIVE', 'PROMOTED', 'RETRACTED', 'SUPERSEDED');

CREATE TYPE repair_type AS ENUM (
    'RECOGNITION', 'REFERENCE', 'SEMANTICS', 'TEMPORALITY', 'FACTUAL_ACCURACY',
    'INTERPRETATION', 'CONTRADICTION', 'SCOPE', 'PRAGMATICS', 'INTERRUPTION',
    'EMOTIONAL_MISATTUNEMENT'
);

CREATE TYPE repair_status AS ENUM ('OPEN', 'REPAIRED', 'DEFERRED', 'HANDED_OFF');

CREATE TYPE obligation_status AS ENUM ('PENDING', 'DUE', 'RESOLVED', 'HANDED_OFF');

CREATE TYPE contradiction_status AS ENUM ('OPEN', 'RECONCILED', 'ESCALATED');

CREATE TYPE causal_relation_status AS ENUM (
    'HYPOTHESIS', 'DISCRIMINATED', 'ADJUDICATED', 'RETRACTED'
);

CREATE TABLE grounded_proposition (
    proposition_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id         UUID NOT NULL REFERENCES session (session_id),
    content            TEXT NOT NULL,
    concept_json       JSONB,
    epistemic_level    epistemic_level NOT NULL,
    grounding_evidence_json JSONB NOT NULL, -- list[str]; never empty (INV enforced in app layer)
    source_assertion_ids_json JSONB NOT NULL DEFAULT '[]',
    established_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    superseded_by       UUID REFERENCES grounded_proposition (proposition_id)
);
CREATE INDEX idx_grounded_proposition_session_id ON grounded_proposition (session_id);

CREATE TABLE conversational_hypothesis (
    hypothesis_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID NOT NULL REFERENCES session (session_id),
    content             TEXT NOT NULL,
    epistemic_level     epistemic_level NOT NULL,
    status              hypothesis_status NOT NULL DEFAULT 'ACTIVE',
    supporting_observations_json JSONB NOT NULL DEFAULT '[]',
    confidence          DECIMAL,
    promoted_proposition_id UUID REFERENCES grounded_proposition (proposition_id)
);
CREATE INDEX idx_conversational_hypothesis_session_id ON conversational_hypothesis (session_id);

CREATE TABLE prospective_obligation (
    obligation_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID NOT NULL REFERENCES session (session_id),
    content             TEXT NOT NULL,
    source              TEXT NOT NULL,
    priority            salience NOT NULL,
    risk                salience NOT NULL,
    trigger             TEXT,
    deadline            TIMESTAMPTZ,
    status              obligation_status NOT NULL DEFAULT 'PENDING',
    resulting_task_id   UUID REFERENCES task (task_id)
);
CREATE INDEX idx_prospective_obligation_session_id ON prospective_obligation (session_id);

CREATE TABLE repair_requirement (
    repair_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID NOT NULL REFERENCES session (session_id),
    turn_id             UUID REFERENCES turn (turn_id),
    repair_type         repair_type NOT NULL,
    description         TEXT NOT NULL,
    materiality         materiality NOT NULL,
    status              repair_status NOT NULL DEFAULT 'OPEN',
    ai_self_repair      BOOLEAN NOT NULL DEFAULT false,
    deferred_reason     TEXT,
    obligation_id       UUID REFERENCES prospective_obligation (obligation_id),
    -- Mirrors periop_core.model_layer.RepairRequirement's app-level
    -- validator: DEFERRED requires both a reason and a linked obligation.
    CONSTRAINT repair_deferred_requires_reason_and_obligation CHECK (
        status <> 'DEFERRED' OR (deferred_reason IS NOT NULL AND obligation_id IS NOT NULL)
    )
);
CREATE INDEX idx_repair_requirement_session_id ON repair_requirement (session_id);
CREATE INDEX idx_repair_requirement_status ON repair_requirement (status);
CREATE INDEX idx_repair_requirement_materiality ON repair_requirement (materiality);

CREATE TABLE contradiction (
    contradiction_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID NOT NULL REFERENCES session (session_id),
    description         TEXT NOT NULL,
    involved_ids_json   JSONB NOT NULL, -- list[uuid] as strings; >=2 (app-level invariant)
    status              contradiction_status NOT NULL DEFAULT 'OPEN',
    promoted_conflict_id UUID REFERENCES conflict (conflict_id)
);
CREATE INDEX idx_contradiction_session_id ON contradiction (session_id);

CREATE TABLE uncertainty (
    uncertainty_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID NOT NULL REFERENCES session (session_id),
    concept_json        JSONB,
    description         TEXT NOT NULL,
    kind                TEXT NOT NULL DEFAULT 'AMBIGUITY',
    resolved            BOOLEAN NOT NULL DEFAULT false
);
CREATE INDEX idx_uncertainty_session_id ON uncertainty (session_id);

CREATE TABLE causal_hypothesis (
    causal_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID NOT NULL REFERENCES session (session_id),
    cause               TEXT NOT NULL,
    effect              TEXT NOT NULL,
    supporting_evidence_json JSONB NOT NULL DEFAULT '[]',
    alternatives_json   JSONB NOT NULL DEFAULT '[]',
    confidence          DECIMAL NOT NULL,
    status              causal_relation_status NOT NULL DEFAULT 'HYPOTHESIS',
    adjudicated_by      TEXT,
    -- Mirrors periop_core.model_layer.CausalHypothesis's app-level
    -- validator: ADJUDICATED requires an explicit clinician marker.
    CONSTRAINT causal_adjudication_requires_marker CHECK (
        status <> 'ADJUDICATED' OR adjudicated_by IS NOT NULL
    )
);
CREATE INDEX idx_causal_hypothesis_session_id ON causal_hypothesis (session_id);

-- One row per session (upsert), unlike the list-shaped tables above.
CREATE TABLE psychological_safety_state (
    session_id          UUID PRIMARY KEY REFERENCES session (session_id),
    estimate             DECIMAL NOT NULL,
    evidence_signals_json JSONB NOT NULL DEFAULT '[]',
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT psychological_safety_estimate_bounded CHECK (estimate >= 0 AND estimate <= 1)
);
