import uuid

import pytest
from pydantic import ValidationError

from periop_core.enums import (
    CausalRelationStatus,
    ContradictionStatus,
    EpistemicLevel,
    Materiality,
    ObligationStatus,
    RepairStatus,
    RepairType,
    Salience,
)
from periop_core.model_layer import (
    CausalHypothesis,
    ConversationalHypothesis,
    ConversationStateEnvelope,
    Contradiction,
    GroundedProposition,
    PersonalAdaptationState,
    ProspectiveObligation,
    PsychologicalSafetyState,
    RepairRequirement,
)


def test_grounded_proposition_requires_grounding_evidence():
    with pytest.raises(ValidationError, match="grounding_evidence"):
        GroundedProposition(
            session_id=uuid.uuid4(),
            content="patient has heart failure",
            epistemic_level=EpistemicLevel.L4_PATIENT_GROUNDED,
            grounding_evidence=[],
        )


def test_grounded_proposition_cannot_be_below_l4():
    with pytest.raises(ValidationError, match="L4_PATIENT_GROUNDED"):
        GroundedProposition(
            session_id=uuid.uuid4(),
            content="patient has heart failure",
            epistemic_level=EpistemicLevel.L3_CLINICAL_HYPOTHESIS,
            grounding_evidence=["turn:abc"],
        )


def test_grounded_proposition_accepts_l4_and_above():
    for level in (
        EpistemicLevel.L4_PATIENT_GROUNDED,
        EpistemicLevel.L5_EXTERNALLY_VERIFIED,
        EpistemicLevel.L6_CLINICALLY_ADJUDICATED,
    ):
        GroundedProposition(
            session_id=uuid.uuid4(),
            content="x",
            epistemic_level=level,
            grounding_evidence=["turn:abc"],
        )


def test_conversational_hypothesis_cannot_hold_grounded_level():
    with pytest.raises(ValidationError, match="cannot be projected as fact"):
        ConversationalHypothesis(
            session_id=uuid.uuid4(),
            content="maybe a pulmonary embolism",
            epistemic_level=EpistemicLevel.L4_PATIENT_GROUNDED,
        )


def test_repair_deferral_requires_reason_and_obligation():
    with pytest.raises(ValidationError, match="deferred_reason"):
        RepairRequirement(
            session_id=uuid.uuid4(),
            repair_type=RepairType.CONTRADICTION,
            description="patient said two different things",
            materiality=Materiality.MODERATE,
            status=RepairStatus.DEFERRED,
        )

    with pytest.raises(ValidationError, match="6A.15"):
        RepairRequirement(
            session_id=uuid.uuid4(),
            repair_type=RepairType.CONTRADICTION,
            description="patient said two different things",
            materiality=Materiality.MODERATE,
            status=RepairStatus.DEFERRED,
            deferred_reason="will revisit when medication topic recurs",
        )


def test_repair_deferral_succeeds_with_reason_and_obligation():
    obligation_id = uuid.uuid4()
    repair = RepairRequirement(
        session_id=uuid.uuid4(),
        repair_type=RepairType.CONTRADICTION,
        description="patient said two different things",
        materiality=Materiality.MODERATE,
        status=RepairStatus.DEFERRED,
        deferred_reason="will revisit when medication topic recurs",
        obligation_id=obligation_id,
    )
    assert repair.obligation_id == obligation_id


def test_contradiction_requires_at_least_two_involved_ids():
    with pytest.raises(ValidationError, match="at least two"):
        Contradiction(
            session_id=uuid.uuid4(),
            description="only one thing referenced",
            involved_ids=[uuid.uuid4()],
        )


def test_causal_hypothesis_adjudication_requires_marker():
    with pytest.raises(ValidationError, match="ADJUDICATED"):
        CausalHypothesis(
            session_id=uuid.uuid4(),
            cause="recent antibiotic",
            effect="rash",
            confidence=0.6,
            status=CausalRelationStatus.ADJUDICATED,
        )

    # Succeeds with the marker.
    ch = CausalHypothesis(
        session_id=uuid.uuid4(),
        cause="recent antibiotic",
        effect="rash",
        confidence=0.6,
        status=CausalRelationStatus.ADJUDICATED,
        adjudicated_by="dr-smith",
    )
    assert ch.adjudicated_by == "dr-smith"


def test_causal_hypothesis_confidence_bounded():
    with pytest.raises(ValidationError):
        CausalHypothesis(
            session_id=uuid.uuid4(), cause="a", effect="b", confidence=1.5
        )


def test_psychological_safety_estimate_bounded():
    with pytest.raises(ValidationError):
        PsychologicalSafetyState(session_id=uuid.uuid4(), estimate=1.2)
    ps = PsychologicalSafetyState(session_id=uuid.uuid4(), estimate=0.7)
    assert ps.estimate == 0.7


def test_personal_adaptation_humour_receptivity_bounded():
    with pytest.raises(ValidationError):
        PersonalAdaptationState(session_id=uuid.uuid4(), humour_receptivity=2.0)
    state = PersonalAdaptationState(session_id=uuid.uuid4())
    assert state.humour_receptivity is None  # conservative default, never guessed


def test_envelope_rejects_overlapping_recommended_and_prohibited_actions():
    from periop_core.enums import ActionType

    with pytest.raises(ValidationError, match="cannot be both recommended and prohibited"):
        ConversationStateEnvelope(
            session_id=uuid.uuid4(),
            active_focus="cardiovascular",
            recommended_action_classes=[ActionType.CLARIFY],
            prohibited_action_classes=[ActionType.CLARIFY],
        )


def test_prospective_obligation_has_no_silent_expiry_state():
    obligation = ProspectiveObligation(
        session_id=uuid.uuid4(),
        content="check for anticoagulant last-dose timing later",
        source="repair:abc",
        priority=Salience.HIGH,
        risk=Salience.HIGH,
    )
    assert obligation.status == ObligationStatus.PENDING
    # Only RESOLVED/HANDED_OFF exist as terminal states in ObligationStatus.
    assert ObligationStatus.RESOLVED in ObligationStatus
    assert ObligationStatus.HANDED_OFF in ObligationStatus
    assert not any("EXPIRE" in member.value for member in ObligationStatus)
