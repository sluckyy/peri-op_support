"""Requirement activation and information-gap computation (§5, Full Spec).

Known simplification (documented, not hidden): matching a WorkingFact to a
Requirement uses `concept.code == requirement_id` — i.e. this assumes
assertions are tagged with the Clinical Dataset Concept_ID directly as
their concept code. The real system resolves this via the (unbuilt) 344-
row Concept Mapping register between free-text/terminology concepts and
Concept_IDs. See docs/exports/clinical_dataset_v1.0.csv for the
Concept_ID -> concept vocabulary this stands in for.

Activation rules (`Requirement.activation_rule`, the dataset's `Trigger`
column) are free text in the source dataset (e.g. "All patients",
"Condition-triggered..."). This module only implements the M0 (universal
mandatory) case as "always active" and treats every other class as
"active" too for now (i.e. it does not yet parse conditional triggers) --
that parser is a documented TODO, not silently assumed equivalent to M0.
"""
from __future__ import annotations

from periop_core.enums import GapStatus, GapType, InformationState, RequirementClass
from periop_core.models import InformationGap, Requirement, RequirementState, WorkingFact

# States that satisfy a requirement outright: no gap should be generated.
_SATISFIED_STATES = {
    InformationState.KNOWN_CONFIRMED,
    InformationState.NOT_APPLICABLE,
}

# Priority weighting by requirement class -- deterministic, not LLM-derived
# (Reconciliation/Gap prioritisation, §5.3: "safety criticality, decision
# impact ... should be deterministic").
_CLASS_PRIORITY_WEIGHT = {
    RequirementClass.M0: 1.0,
    RequirementClass.M1: 0.8,
    RequirementClass.C1: 0.6,
    RequirementClass.C2: 0.6,
    RequirementClass.C3: 0.6,
    RequirementClass.C4: 0.5,
    RequirementClass.O: 0.1,
}

_GAP_TYPE_FOR_STATE = {
    InformationState.NOT_ASKED: GapType.MISSING,
    InformationState.PARTIAL: GapType.PARTIAL,
    InformationState.STALE: GapType.STALE,
    InformationState.KNOWN_UNCONFIRMED: GapType.UNVERIFIED,
    InformationState.CONFLICTING: GapType.CONFLICTING,
    InformationState.UNAVAILABLE: GapType.UNAVAILABLE_SOURCE,
    InformationState.DEFERRED: GapType.DEFERRED,
    InformationState.SAFETY_ESCALATED: GapType.SAFETY_ESCALATED,
    InformationState.UNKNOWN: GapType.MISSING,
    InformationState.DECLINED: GapType.MISSING,
}


def evaluate_requirements(
    session_id,
    requirements: dict[str, Requirement],
    working_facts_by_requirement: dict[str, WorkingFact],
) -> list[RequirementState]:
    """Compute one RequirementState per active requirement.

    A requirement with no matching WorkingFact is NOT_ASKED (INV-005:
    this must never be silently treated as a negative/confirmed-absent
    finding).
    """
    states: list[RequirementState] = []
    for requirement_id, requirement in requirements.items():
        fact = working_facts_by_requirement.get(requirement_id)
        if fact is None:
            information_state = InformationState.NOT_ASKED
            evidence_refs = []
        else:
            information_state = _information_state_for_fact(fact)
            evidence_refs = list(fact.supporting_assertion_ids) + list(
                fact.dissenting_assertion_ids
            )
        states.append(
            RequirementState(
                session_id=session_id,
                requirement_id=requirement_id,
                information_state=information_state,
                evidence_refs=evidence_refs,
            )
        )
    return states


def _information_state_for_fact(fact: WorkingFact) -> InformationState:
    from periop_core.enums import VerificationState

    if fact.verification_state == VerificationState.CONFLICTED:
        return InformationState.CONFLICTING
    if fact.verification_state == VerificationState.CONFIRMED:
        return InformationState.KNOWN_CONFIRMED
    if fact.verification_state == VerificationState.STALE:
        return InformationState.STALE
    if fact.verification_state == VerificationState.UNKNOWN:
        return InformationState.UNKNOWN
    return InformationState.KNOWN_UNCONFIRMED


def compute_gaps(
    requirement_states: list[RequirementState],
    requirements: dict[str, Requirement],
) -> list[InformationGap]:
    """INV-006: a NOT_APPLICABLE requirement cannot generate an active gap
    -- enforced here by simply never emitting one for that state (and for
    already-KNOWN_CONFIRMED requirements, which need no gap either)."""
    gaps: list[InformationGap] = []
    for state in requirement_states:
        if state.information_state in _SATISFIED_STATES:
            continue
        requirement = requirements[state.requirement_id]
        gap_type = _GAP_TYPE_FOR_STATE.get(state.information_state, GapType.MISSING)
        priority = _CLASS_PRIORITY_WEIGHT.get(requirement.requiredness, 0.5)
        # Conflicting/safety-escalated gaps always outrank plain missing
        # data, regardless of requirement class (§5.3: safety criticality
        # first).
        if gap_type in (GapType.CONFLICTING, GapType.SAFETY_ESCALATED):
            priority = max(priority, 0.9)
        gaps.append(
            InformationGap(
                requirement_state_id=state.requirement_state_id,
                gap_type=gap_type,
                priority_score=priority,
                status=GapStatus.OPEN,
            )
        )
    return gaps
