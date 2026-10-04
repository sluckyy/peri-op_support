import uuid

from periop_core.enums import (
    GapType,
    InformationState,
    RequirementClass,
    VerificationState,
)
from periop_core.gap_engine import compute_gaps, evaluate_requirements
from periop_core.models import ConceptReference, Requirement, RequirementState, WorkingFact


def _requirement(req_id, klass):
    return Requirement(requirement_id=req_id, activation_rule="All patients", requiredness=klass)


def test_unresolved_requirement_is_not_asked_not_a_silent_negative():
    session_id = uuid.uuid4()
    requirements = {"CTX-003": _requirement("CTX-003", RequirementClass.M0)}

    states = evaluate_requirements(session_id, requirements, working_facts_by_requirement={})

    assert len(states) == 1
    assert states[0].information_state == InformationState.NOT_ASKED
    assert states[0].evidence_refs == []


def test_confirmed_fact_generates_no_gap():
    session_id = uuid.uuid4()
    requirements = {"CTX-003": _requirement("CTX-003", RequirementClass.M0)}
    fact = WorkingFact(
        session_id=session_id,
        concept=ConceptReference(original_text="procedure"),
        verification_state=VerificationState.CONFIRMED,
        supporting_assertion_ids=[uuid.uuid4()],
    )

    states = evaluate_requirements(
        session_id, requirements, working_facts_by_requirement={"CTX-003": fact}
    )
    gaps = compute_gaps(states, requirements)

    assert states[0].information_state == InformationState.KNOWN_CONFIRMED
    assert gaps == []


def test_not_applicable_requirement_never_generates_a_gap():
    # INV-006, exercised directly at this layer.
    session_id = uuid.uuid4()
    requirements = {"GOAL-020": _requirement("GOAL-020", RequirementClass.M1)}
    state = RequirementState(
        session_id=session_id,
        requirement_id="GOAL-020",
        information_state=InformationState.NOT_APPLICABLE,
    )

    gaps = compute_gaps([state], requirements)

    assert gaps == []


def test_conflicting_fact_outranks_plain_missing_data_within_the_same_requirement_class():
    """§5.3: safety criticality comes before requirement class in
    prioritisation. Demonstrated here within a single class (O) so the
    comparison is apples-to-apples: a conflict on an optional field still
    gets boosted above a merely-missing optional field.

    Note: this does NOT claim a conflict on an optional field outranks a
    missing M0 (universal mandatory) field -- the current implementation
    still lets M0's base weight (1.0) beat a boosted conflict (0.9) on a
    lower class, which is a defensible ordering, not an oversight, but is
    worth knowing about if you tune _CLASS_PRIORITY_WEIGHT later."""
    session_id = uuid.uuid4()
    requirements = {
        "OPT-001": _requirement("OPT-001", RequirementClass.O),
        "OPT-002": _requirement("OPT-002", RequirementClass.O),
    }
    conflicted_fact = WorkingFact(
        session_id=session_id,
        concept=ConceptReference(original_text="x"),
        verification_state=VerificationState.CONFLICTED,
        supporting_assertion_ids=[uuid.uuid4(), uuid.uuid4()],
    )

    states = evaluate_requirements(
        session_id,
        requirements,
        working_facts_by_requirement={"OPT-001": conflicted_fact},
    )
    gaps = compute_gaps(states, requirements)
    gaps_by_requirement = {
        s.requirement_id: g
        for s in states
        for g in gaps
        if g.requirement_state_id == s.requirement_state_id
    }

    conflict_gap = gaps_by_requirement["OPT-001"]
    missing_gap = gaps_by_requirement["OPT-002"]
    assert conflict_gap.gap_type == GapType.CONFLICTING
    assert missing_gap.gap_type == GapType.MISSING
    assert conflict_gap.priority_score > missing_gap.priority_score


def test_stale_working_fact_generates_a_stale_gap_not_silently_confirmed():
    """periop_core.reconciliation now actually produces STALE (freshness
    assessment, step 3) -- this exercises the downstream path that was
    already built (InformationState.STALE, GapType.STALE) but previously
    unreachable, since nothing ever set VerificationState.STALE before."""
    session_id = uuid.uuid4()
    requirements = {"CUR-002": _requirement("CUR-002", RequirementClass.M0)}
    stale_fact = WorkingFact(
        session_id=session_id,
        concept=ConceptReference(original_text="recent health change"),
        verification_state=VerificationState.STALE,
        freshness={"classification": "STALE"},
        supporting_assertion_ids=[uuid.uuid4()],
    )

    states = evaluate_requirements(
        session_id, requirements, working_facts_by_requirement={"CUR-002": stale_fact}
    )
    gaps = compute_gaps(states, requirements)

    assert states[0].information_state == InformationState.STALE
    assert len(gaps) == 1
    assert gaps[0].gap_type == GapType.STALE
