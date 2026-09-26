import uuid

from periop_core.enums import (
    CausalRelationStatus,
    EpistemicLevel,
    Materiality,
    RepairStatus,
    RepairType,
)
from periop_core.model_layer import CausalHypothesis, ConversationalHypothesis, GroundedProposition
from periop_core.model_layer_gate import (
    find_dependents,
    reference_string,
    required_repair_for_correction,
)
from periop_core.safety import ClosureOutcome, evaluate_closure


def test_reference_string_convention():
    obj_id = uuid.uuid4()
    assert reference_string("proposition", obj_id) == f"proposition:{obj_id}"


def test_find_dependents_locates_hypothesis_and_proposition_and_causal_hypothesis():
    session_id = uuid.uuid4()
    superseded_id = uuid.uuid4()
    ref = reference_string("proposition", superseded_id)

    dependent_hyp = ConversationalHypothesis(
        session_id=session_id,
        content="possibly related to the earlier finding",
        supporting_observations=[ref],
    )
    independent_hyp = ConversationalHypothesis(
        session_id=session_id, content="unrelated", supporting_observations=["plain note"]
    )
    dependent_prop = GroundedProposition(
        session_id=session_id,
        content="downstream conclusion",
        epistemic_level=EpistemicLevel.L4_PATIENT_GROUNDED,
        grounding_evidence=[ref],
    )
    dependent_causal = CausalHypothesis(
        session_id=session_id,
        cause="the now-corrected finding",
        effect="observed symptom",
        confidence=0.4,
        supporting_evidence=[ref],
    )

    result = find_dependents(
        ref,
        hypotheses=[dependent_hyp, independent_hyp],
        propositions=[dependent_prop],
        causal_hypotheses=[dependent_causal],
    )

    assert result.dependent_hypotheses == [dependent_hyp]
    assert result.dependent_propositions == [dependent_prop]
    assert result.dependent_causal_hypotheses == [dependent_causal]
    assert result.total_count() == 3
    assert result.is_empty() is False


def test_find_dependents_empty_when_nothing_references_it():
    result = find_dependents("proposition:nonexistent")
    assert result.is_empty() is True
    assert result.total_count() == 0


def test_correction_with_dependents_produces_high_materiality_repair():
    session_id = uuid.uuid4()
    ref = reference_string("proposition", uuid.uuid4())
    dependent_hyp = ConversationalHypothesis(
        session_id=session_id, content="x", supporting_observations=[ref]
    )
    dependents = find_dependents(ref, hypotheses=[dependent_hyp])

    repair = required_repair_for_correction(ref, dependents, session_id=session_id)
    assert repair.materiality == Materiality.HIGH
    assert repair.status == RepairStatus.OPEN
    assert repair.repair_type == RepairType.FACTUAL_ACCURACY
    assert "1 hypothesis(es)" in repair.description


def test_correction_with_no_dependents_still_produces_a_low_materiality_repair():
    ref = reference_string("proposition", uuid.uuid4())
    dependents = find_dependents(ref)
    repair = required_repair_for_correction(ref, dependents, session_id=uuid.uuid4())
    assert repair.materiality == Materiality.LOW
    assert repair.status == RepairStatus.OPEN  # corrections are never silent


def test_critical_open_repair_blocks_closure():
    session_id = uuid.uuid4()
    from periop_core.model_layer import RepairRequirement

    repair = RepairRequirement(
        session_id=session_id,
        repair_type=RepairType.CONTRADICTION,
        description="patient's account of the difficult airway conflicts with itself",
        materiality=Materiality.CRITICAL,
        status=RepairStatus.OPEN,
    )
    result = evaluate_closure(
        open_tasks=[], agenda_items=[], conflicts=[], repair_requirements=[repair]
    )
    assert result.outcome == ClosureOutcome.BLOCKED
    assert any("6A.15" in r for r in result.blocking_reasons)


def test_moderate_open_repair_downgrades_but_does_not_block():
    session_id = uuid.uuid4()
    from periop_core.model_layer import RepairRequirement

    repair = RepairRequirement(
        session_id=session_id,
        repair_type=RepairType.SEMANTICS,
        description="ambiguous phrasing about medication timing",
        materiality=Materiality.MODERATE,
        status=RepairStatus.OPEN,
    )
    result = evaluate_closure(
        open_tasks=[], agenda_items=[], conflicts=[], repair_requirements=[repair]
    )
    assert result.outcome == ClosureOutcome.COMPLETE_WITH_OPEN_ACTIONS


def test_repaired_status_repair_does_not_affect_closure():
    session_id = uuid.uuid4()
    from periop_core.model_layer import RepairRequirement

    repair = RepairRequirement(
        session_id=session_id,
        repair_type=RepairType.REFERENCE,
        description="clarified which medication the patient meant",
        materiality=Materiality.CRITICAL,
        status=RepairStatus.REPAIRED,
    )
    result = evaluate_closure(
        open_tasks=[], agenda_items=[], conflicts=[], repair_requirements=[repair]
    )
    assert result.outcome == ClosureOutcome.COMPLETE
