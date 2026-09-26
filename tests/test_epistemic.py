import uuid

import pytest

from periop_core.enums import EpistemicLevel, HypothesisStatus
from periop_core.epistemic import PromotionNotPermitted, can_promote, promote_to_grounded_proposition
from periop_core.model_layer import ConversationalHypothesis


def test_l2_to_l4_blocked_without_grounding():
    allowed, reasons = can_promote(
        EpistemicLevel.L2_PRAGMATIC_INTERPRETATION,
        EpistemicLevel.L4_PATIENT_GROUNDED,
        has_grounding_evidence=False,
        has_clinician_adjudication=False,
    )
    assert allowed is False
    assert any("grounding" in r.lower() for r in reasons)


def test_l2_to_l4_allowed_with_grounding():
    allowed, reasons = can_promote(
        EpistemicLevel.L2_PRAGMATIC_INTERPRETATION,
        EpistemicLevel.L4_PATIENT_GROUNDED,
        has_grounding_evidence=True,
        has_clinician_adjudication=False,
    )
    assert allowed is True


def test_l3_to_l6_blocked_without_clinician_adjudication():
    allowed, reasons = can_promote(
        EpistemicLevel.L3_CLINICAL_HYPOTHESIS,
        EpistemicLevel.L6_CLINICALLY_ADJUDICATED,
        has_grounding_evidence=True,  # grounding present but adjudication absent
        has_clinician_adjudication=False,
    )
    assert allowed is False
    assert any("adjudication" in r.lower() for r in reasons)


def test_l3_to_l6_allowed_with_both_gates_satisfied():
    allowed, reasons = can_promote(
        EpistemicLevel.L3_CLINICAL_HYPOTHESIS,
        EpistemicLevel.L6_CLINICALLY_ADJUDICATED,
        has_grounding_evidence=True,
        has_clinician_adjudication=True,
    )
    assert allowed is True


def test_non_monotonic_promotion_rejected():
    allowed, reasons = can_promote(
        EpistemicLevel.L4_PATIENT_GROUNDED,
        EpistemicLevel.L2_PRAGMATIC_INTERPRETATION,
        has_grounding_evidence=True,
        has_clinician_adjudication=True,
    )
    assert allowed is False
    assert any("monotonic" in r.lower() for r in reasons)


def test_same_level_promotion_rejected():
    allowed, _ = can_promote(
        EpistemicLevel.L2_PRAGMATIC_INTERPRETATION,
        EpistemicLevel.L2_PRAGMATIC_INTERPRETATION,
        has_grounding_evidence=True,
        has_clinician_adjudication=True,
    )
    assert allowed is False


def test_promote_to_grounded_proposition_end_to_end():
    hypothesis = ConversationalHypothesis(
        session_id=uuid.uuid4(),
        content="possible penicillin allergy",
        epistemic_level=EpistemicLevel.L2_PRAGMATIC_INTERPRETATION,
    )

    updated_hypothesis, proposition = promote_to_grounded_proposition(
        hypothesis,
        target_level=EpistemicLevel.L4_PATIENT_GROUNDED,
        grounding_evidence=["patient confirmed throat swelling after penicillin"],
    )

    assert updated_hypothesis.status == HypothesisStatus.PROMOTED
    assert updated_hypothesis.promoted_proposition_id == proposition.proposition_id
    assert proposition.epistemic_level == EpistemicLevel.L4_PATIENT_GROUNDED
    assert proposition.session_id == hypothesis.session_id
    # Original hypothesis object is untouched (treated as immutable).
    assert hypothesis.status == HypothesisStatus.ACTIVE


def test_promote_raises_when_ungrounded():
    hypothesis = ConversationalHypothesis(
        session_id=uuid.uuid4(),
        content="possible penicillin allergy",
        epistemic_level=EpistemicLevel.L2_PRAGMATIC_INTERPRETATION,
    )
    with pytest.raises(PromotionNotPermitted):
        promote_to_grounded_proposition(
            hypothesis,
            target_level=EpistemicLevel.L4_PATIENT_GROUNDED,
            grounding_evidence=[],
        )
