from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from periop_core.enums import (
    AssertionState,
    Certainty,
    EpistemicLevel,
    Materiality,
    RepairStatus,
    RepairType,
    Salience,
    Speaker,
)
from periop_core.model_layer import (
    ConversationalHypothesis,
    GroundedProposition,
    ProspectiveObligation,
    PsychologicalSafetyState,
    RepairRequirement,
)
from periop_core.models import (
    Conflict,
    InformationGap,
    OpenTask,
    PatientAgendaItem,
    RequirementState,
    Session,
    WorkingFact,
)
from periop_core.safety import ClosureOutcome


class CreateSessionRequest(BaseModel):
    subject_ref: str
    encounter_ref: str | None = None
    procedure_context: dict[str, Any] = {}

    age_years: int | None = None
    age_source: str = "self_declared"
    is_obstetric_procedure: bool | None = False
    is_obstetric_source: str = "self_declared"
    is_emergency_listing: bool | None = False
    is_emergency_source: str = "self_declared"


class SessionRejectedResponse(BaseModel):
    reasons: list[str]


class AddAssertionRequest(BaseModel):
    """Demo shortcut -- see periop_api/__init__.py docstring. In the real
    system this is never a direct client-facing endpoint; assertions come
    only from validated LLM extraction over a patient Turn."""

    concept_code: str  # Clinical Dataset Concept_ID, e.g. "ALL-003"
    concept_text: str | None = None  # defaults to the dataset's concept label
    value: Any | None = None
    assertion_state: AssertionState
    certainty: Certainty = Certainty.EXPLICIT
    source_type: str  # e.g. "PATIENT", "EMR", "PROXY"
    speaker: Speaker = Speaker.PATIENT
    # Demo-only: lets the form backdate an assertion to exercise
    # reconciliation's freshness assessment (step 3). The real system
    # would derive this from Assertion.event_time / the actual conversation
    # turn timestamp, never a client-supplied field -- see periop_api's
    # module docstring on demo shortcuts.
    assertion_time: datetime | None = None


class GapWithLabel(BaseModel):
    gap: InformationGap
    requirement_id: str
    domain: str | None = None
    concept: str | None = None


class ClosurePreview(BaseModel):
    outcome: ClosureOutcome
    blocking_reasons: list[str]
    open_action_reasons: list[str]


class SessionSummary(BaseModel):
    session: Session
    working_facts: list[WorkingFact]
    conflicts: list[Conflict]
    requirement_states: list[RequirementState]
    gaps: list[GapWithLabel]
    tasks: list[OpenTask]
    agenda_items: list[PatientAgendaItem]
    closure_preview: ClosurePreview
    # v1.1 Model Layer (§6A) -- see periop_core.model_layer
    hypotheses: list[ConversationalHypothesis] = []
    propositions: list[GroundedProposition] = []
    obligations: list[ProspectiveObligation] = []
    repairs: list[RepairRequirement] = []
    psychological_safety: PsychologicalSafetyState | None = None


class ConceptOption(BaseModel):
    concept_id: str
    domain: str
    concept: str
    patient_question: str
    requirement_class: str


# ============================================================
# v1.1 Model Layer (§6A) request/response schemas
# ============================================================


class CreateHypothesisRequest(BaseModel):
    content: str
    epistemic_level: EpistemicLevel = EpistemicLevel.L2_PRAGMATIC_INTERPRETATION
    supporting_observations: list[str] = []
    confidence: float | None = None


class PromoteHypothesisRequest(BaseModel):
    target_level: EpistemicLevel = EpistemicLevel.L4_PATIENT_GROUNDED
    grounding_evidence: list[str]
    has_clinician_adjudication: bool = False


class PromoteHypothesisResponse(BaseModel):
    hypothesis: ConversationalHypothesis
    proposition: GroundedProposition


class PromotionRejectedResponse(BaseModel):
    reasons: list[str]


class CreateObligationRequest(BaseModel):
    content: str
    source: str
    priority: Salience = Salience.MODERATE
    risk: Salience = Salience.MODERATE
    trigger: str | None = None
    deadline: datetime | None = None


class CreateRepairRequest(BaseModel):
    repair_type: RepairType
    description: str
    materiality: Materiality
    status: RepairStatus = RepairStatus.OPEN
    ai_self_repair: bool = False
    deferred_reason: str | None = None
    obligation_id: uuid.UUID | None = None
    # Convenience: create-and-link an obligation in the same call rather
    # than requiring the client to call the obligations endpoint first,
    # get an id back, then call this one. If both `obligation_id` and
    # `create_obligation` are given, `create_obligation` wins.
    create_obligation: CreateObligationRequest | None = None


class RepairValidationErrorResponse(BaseModel):
    message: str


class PsychologicalSafetySignalRequest(BaseModel):
    signal_names: list[str]


class HumourCheckRequest(BaseModel):
    feature_enabled: bool = False
    proposed_target: str = "self"
    high_distress: bool = False
    serious_safety_disclosure_active: bool = False
    conflict_present: bool = False
    bereavement_context: bool = False
    receptivity_known: bool = False
    implies_incompetence: bool = False


class HumourCheckResponse(BaseModel):
    permitted: bool
    reasons: list[str]


class CausalEcdRequest(BaseModel):
    prior: dict[str, float]
    likelihoods: dict[str, dict[str, float]]


class CausalEcdResponse(BaseModel):
    prior_entropy: float
    expected_posterior_entropy: float
    ecd: float
