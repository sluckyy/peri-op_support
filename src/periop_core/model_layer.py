"""Canonical objects for the v1.1 Model Layer (Full Spec §6A), sitting
between raw conversation and the (not yet built) Conversation
Orchestrator — see
docs/exports/full_project_specification_v1.1_model_layer.md.

These are conversational-cognition objects, not clinical-truth objects:
none of them may be treated as an authoritative clinical fact (that
remains WorkingFact's job, in periop_core.models). A
ConversationalHypothesis or GroundedProposition existing here says
nothing about clinical truth on its own -- it becomes clinically
actionable only once (if ever) it is used to produce an Assertion through
the ordinary reconciliation path.

Two relationships to existing periop_core.models objects are deliberately
NOT collapsed, even though they look similar:

- Contradiction (here) vs. Conflict (periop_core.models): a Contradiction
  is a conversation-layer detection -- "these two things the patient/
  system said don't fit together" -- that may exist before, or instead
  of, a clinical Conflict. Promoting a Contradiction into a formal
  Conflict (once it concerns two actual Assertions about the same
  clinical concept) is a reconciliation-layer decision; a Contradiction
  can carry `promoted_conflict_id` once that happens, but plenty of
  contradictions (e.g. two interpretations of ambiguous phrasing) never
  need to become one.
- ProspectiveObligation (here) vs. OpenTask (periop_core.models): a
  ProspectiveObligation is a conversational "remember to come back to
  this" note generated and resolved within the conversation itself (e.g.
  "clarify vague answer once the topic naturally recurs"). OpenTask is a
  workflow-layer human/retrieval obligation. A ProspectiveObligation that
  cannot be resolved conversationally should result in an OpenTask being
  created (`resulting_task_id`), not be silently treated as the same
  thing.

Scope honestly stated: this module implements the *data model* and the
invariants that are checkable on construction. The scoring/reasoning that
would normally populate these objects (attention scoring, epistemic
promotion checks, causal ECD, psychological-safety estimation, humour
gating) lives in the sibling modules periop_core.epistemic,
periop_core.attention, periop_core.causal_reasoning,
periop_core.psychological_safety and periop_core.humour_policy. None of
this is wired to an LLM extractor yet -- Phase 2 (§18.1) is not built.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from periop_core.enums import (
    ActionType,
    CausalRelationStatus,
    ContradictionStatus,
    EpistemicLevel,
    HypothesisStatus,
    Materiality,
    ObligationStatus,
    RepairStatus,
    RepairType,
    Salience,
)
from periop_core.models import ConceptReference


def _uuid4() -> uuid.UUID:
    return uuid.uuid4()


class GroundedProposition(BaseModel):
    """Table 9: 'Meaning sufficiently established with the patient or
    verified source.' Must retain source and grounding evidence -- both
    enforced below. Floored at L4 (patient-grounded): anything less
    grounded is a ConversationalHypothesis, not a GroundedProposition."""

    proposition_id: uuid.UUID = Field(default_factory=_uuid4)
    session_id: uuid.UUID
    content: str
    concept: ConceptReference | None = None
    epistemic_level: EpistemicLevel
    grounding_evidence: list[str]  # e.g. turn/assertion references, human-readable
    source_assertion_ids: list[uuid.UUID] = Field(default_factory=list)
    established_at: datetime = Field(default_factory=datetime.utcnow)
    superseded_by: uuid.UUID | None = None

    @field_validator("grounding_evidence")
    @classmethod
    def _must_have_grounding_evidence(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError(
                "GroundedProposition requires non-empty grounding_evidence "
                "(Table 9 invariant: 'must retain source and grounding evidence')"
            )
        return v

    @field_validator("epistemic_level")
    @classmethod
    def _must_be_at_least_grounded(cls, v: EpistemicLevel) -> EpistemicLevel:
        from periop_core.enums import EPISTEMIC_LEVEL_ORDER

        if EPISTEMIC_LEVEL_ORDER.index(v) < EPISTEMIC_LEVEL_ORDER.index(
            EpistemicLevel.L4_PATIENT_GROUNDED
        ):
            raise ValueError(
                f"GroundedProposition cannot be constructed below "
                f"L4_PATIENT_GROUNDED (got {v}); represent it as a "
                f"ConversationalHypothesis until grounded"
            )
        return v


class ConversationalHypothesis(BaseModel):
    """Table 9: 'Semantic, pragmatic or clinical interpretation not yet
    established.' Cannot be projected as fact -- enforced by capping
    epistemic_level below L4 (once grounding-worthy, it should be
    promoted into a GroundedProposition via periop_core.epistemic, not
    have its level mutated in place)."""

    hypothesis_id: uuid.UUID = Field(default_factory=_uuid4)
    session_id: uuid.UUID
    content: str
    epistemic_level: EpistemicLevel = EpistemicLevel.L2_PRAGMATIC_INTERPRETATION
    status: HypothesisStatus = HypothesisStatus.ACTIVE
    supporting_observations: list[str] = Field(default_factory=list)
    confidence: float | None = None
    promoted_proposition_id: uuid.UUID | None = None

    @field_validator("epistemic_level")
    @classmethod
    def _must_be_below_grounded(cls, v: EpistemicLevel) -> EpistemicLevel:
        from periop_core.enums import EPISTEMIC_LEVEL_ORDER

        if EPISTEMIC_LEVEL_ORDER.index(v) >= EPISTEMIC_LEVEL_ORDER.index(
            EpistemicLevel.L4_PATIENT_GROUNDED
        ):
            raise ValueError(
                "ConversationalHypothesis cannot itself hold an L4+ level "
                "(Table 9: 'cannot be projected as fact'); promote it to "
                "a GroundedProposition instead via periop_core.epistemic"
            )
        return v

    @field_validator("confidence")
    @classmethod
    def _confidence_bounded(cls, v: float | None) -> float | None:
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError("confidence must be in [0, 1]")
        return v


class Uncertainty(BaseModel):
    """Table 9: explicit unresolved ambiguity, missing value or uncertain
    interpretation. Deliberately has no 'value' field: an Uncertainty
    records that something is unresolved, never what it might resolve to
    as if it were an answer -- keeping it structurally distinct from a
    negative finding (Table 9: 'unknown must remain distinct from
    negative')."""

    uncertainty_id: uuid.UUID = Field(default_factory=_uuid4)
    session_id: uuid.UUID
    concept: ConceptReference | None = None
    description: str
    kind: str = "AMBIGUITY"  # AMBIGUITY | MISSING_VALUE | UNCERTAIN_INTERPRETATION
    resolved: bool = False


class Contradiction(BaseModel):
    """Table 9: incompatible assertions or interpretations requiring
    reconciliation. Material conflict cannot be silently resolved -- see
    module docstring for the relationship to periop_core.models.Conflict.
    """

    contradiction_id: uuid.UUID = Field(default_factory=_uuid4)
    session_id: uuid.UUID
    description: str
    involved_ids: list[uuid.UUID]  # hypothesis_id / proposition_id / assertion_id
    status: ContradictionStatus = ContradictionStatus.OPEN
    promoted_conflict_id: uuid.UUID | None = None

    @field_validator("involved_ids")
    @classmethod
    def _needs_at_least_two(cls, v: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(v) < 2:
            raise ValueError("A Contradiction must reference at least two items")
        return v


class RepairRequirement(BaseModel):
    """Table 9 / 6A.4: a detected misunderstanding or error requiring
    repair. Must remain open until repaired, deferred with reason, or
    handed off -- and 6A.15's 'deferral creates an obligation when the
    issue remains relevant' is enforced directly below: DEFERRED requires
    both a reason and a linked ProspectiveObligation.
    """

    repair_id: uuid.UUID = Field(default_factory=_uuid4)
    session_id: uuid.UUID
    turn_id: uuid.UUID | None = None
    repair_type: RepairType
    description: str
    materiality: Materiality
    status: RepairStatus = RepairStatus.OPEN
    ai_self_repair: bool = False
    deferred_reason: str | None = None
    obligation_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _deferral_requires_reason_and_obligation(self) -> "RepairRequirement":
        if self.status == RepairStatus.DEFERRED:
            if not self.deferred_reason:
                raise ValueError("A DEFERRED repair requires deferred_reason")
            if self.obligation_id is None:
                raise ValueError(
                    "6A.15 violation: deferring a RepairRequirement must create a "
                    "ProspectiveObligation (obligation_id is required when DEFERRED)"
                )
        return self


class ProspectiveObligation(BaseModel):
    """Table 9 / 6A.5: a future conversational task with trigger,
    deadline and priority. 'Deferral must not equal forgetting' -- there
    is deliberately no silent-expiry status in ObligationStatus."""

    obligation_id: uuid.UUID = Field(default_factory=_uuid4)
    session_id: uuid.UUID
    content: str
    source: str  # human-readable origin, e.g. "repair:<id>", "hypothesis:<id>"
    priority: Salience
    risk: Salience
    trigger: str | None = None
    deadline: datetime | None = None
    status: ObligationStatus = ObligationStatus.PENDING
    resulting_task_id: uuid.UUID | None = None  # set if escalated to an OpenTask


class CausalHypothesis(BaseModel):
    """Table 9 / 6A.10: a provisional cause-effect explanation with
    alternatives and confidence. Temporal sequence, association and
    causation must remain separate relations -- `status` never implies
    causation was established by the mere fact of being tracked here, and
    ADJUDICATED requires an explicit clinician marker."""

    causal_id: uuid.UUID = Field(default_factory=_uuid4)
    session_id: uuid.UUID
    cause: str
    effect: str
    supporting_evidence: list[str] = Field(default_factory=list)
    alternatives: list[str] = Field(default_factory=list)
    confidence: float
    status: CausalRelationStatus = CausalRelationStatus.HYPOTHESIS
    adjudicated_by: str | None = None

    @field_validator("confidence")
    @classmethod
    def _confidence_bounded(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("confidence must be in [0, 1]")
        return v

    @model_validator(mode="after")
    def _adjudication_requires_marker(self) -> "CausalHypothesis":
        if self.status == CausalRelationStatus.ADJUDICATED and not self.adjudicated_by:
            raise ValueError(
                "6A.10 violation: ADJUDICATED status requires adjudicated_by "
                "(causal hypotheses do not become authoritative causal "
                "assertions without clinician adjudication)"
            )
        return self


class PsychologicalSafetyState(BaseModel):
    """6A.7: PSt = P(interpersonal risk can be taken safely | observations).

    Scope honestly stated: `estimate` is whatever periop_core.
    psychological_safety's heuristic (or, later, a real classifier)
    produces -- this object just carries and bounds it. See that
    module's docstring before treating the estimate as validated.
    """

    session_id: uuid.UUID
    estimate: float
    evidence_signals: list[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("estimate")
    @classmethod
    def _bounded(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("estimate must be in [0, 1]")
        return v


class PersonalAdaptationState(BaseModel):
    """6A.9: theta^P -- session-scoped, subordinate to accessibility,
    safety and patient choice. `humour_receptivity` is explicitly called
    out in the spec as something that 'may be inferred only
    conservatively and should remain uncertain' -- left None by default
    rather than defaulting to a guessed value.
    """

    session_id: uuid.UUID
    open_question_responsiveness: float | None = None
    preferred_specificity: str | None = None
    processing_latency_hint: str | None = None
    verbosity_preference: str | None = None
    correction_pattern: str | None = None
    signposting_need: str | None = None
    uncertainty_expression_preference: str | None = None
    humour_receptivity: float | None = None

    @field_validator("open_question_responsiveness", "humour_receptivity")
    @classmethod
    def _bounded_if_present(cls, v: float | None) -> float | None:
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError("value must be in [0, 1] if provided")
        return v


class ConversationStateEnvelope(BaseModel):
    """Table 11 / 6A.11: what the Model Layer emits to the Orchestrator
    before each governed action selection. The Orchestrator (not built
    yet -- see module docstring) remains responsible for policy
    hierarchy, deterministic safety gates and the actual InterviewAction
    selection; this envelope only describes conversational state and
    recommends/prohibits *classes* of action, per the spec's own framing.
    """

    envelope_id: uuid.UUID = Field(default_factory=_uuid4)
    session_id: uuid.UUID
    active_focus: str
    grounded_refs: list[uuid.UUID] = Field(default_factory=list)
    hypothesis_refs: list[uuid.UUID] = Field(default_factory=list)
    repair_queue: list[uuid.UUID] = Field(default_factory=list)
    obligation_queue: list[uuid.UUID] = Field(default_factory=list)
    patient_agenda: list[uuid.UUID] = Field(default_factory=list)
    psychological_safety: PsychologicalSafetyState | None = None
    narrative_state: dict[str, Any] = Field(default_factory=dict)
    interaction_parameters: PersonalAdaptationState | None = None
    causal_hypotheses: list[uuid.UUID] = Field(default_factory=list)
    recommended_action_classes: list[ActionType] = Field(default_factory=list)
    prohibited_action_classes: list[ActionType] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    @model_validator(mode="after")
    def _no_action_both_recommended_and_prohibited(self) -> "ConversationStateEnvelope":
        overlap = set(self.recommended_action_classes) & set(self.prohibited_action_classes)
        if overlap:
            raise ValueError(
                f"Action classes cannot be both recommended and prohibited: {overlap}"
            )
        return self
