"""Epistemic ladder promotion rules (Full Spec §6A.3 / Table 10).

'Promotion is monotonic only when the required evidence exists. The
system must not infer that an unmentioned item is absent, must not
convert pragmatic implication into a patient assertion and must not
convert a patient report into a diagnosis.'

Two crossings are explicitly gated by the spec:
    L2 -> L4 (or higher) requires grounding evidence
    L3 -> L6 requires clinician adjudication

This module treats those as the general form 'crossing into L4+ requires
grounding' and 'crossing into L6 requires clinician adjudication',
applied from whatever level a hypothesis currently sits at -- not only
from exactly L2 or L3 -- since the spec's own invariant ('promotion is
monotonic only when the required evidence exists') is evidence-gated by
the target level crossed, not by the specific origin level.
"""
from __future__ import annotations

import uuid

from periop_core.enums import EPISTEMIC_LEVEL_ORDER, EpistemicLevel, HypothesisStatus
from periop_core.model_layer import ConversationalHypothesis, GroundedProposition


class PromotionNotPermitted(Exception):
    def __init__(self, reasons: list[str]):
        super().__init__("; ".join(reasons))
        self.reasons = reasons


def _index(level: EpistemicLevel) -> int:
    return EPISTEMIC_LEVEL_ORDER.index(level)


def can_promote(
    current_level: EpistemicLevel,
    target_level: EpistemicLevel,
    *,
    has_grounding_evidence: bool,
    has_clinician_adjudication: bool,
) -> tuple[bool, list[str]]:
    """Return (allowed, reasons). `reasons` is always populated -- with
    the satisfied/violated conditions -- so a caller (or a test) can see
    *why*, not just whether."""
    reasons: list[str] = []

    if _index(target_level) <= _index(current_level):
        reasons.append(
            f"{target_level} is not strictly higher than {current_level}; "
            f"promotion must be monotonic (use retraction/correction for demotion)"
        )
        return False, reasons

    crosses_l4 = _index(target_level) >= _index(EpistemicLevel.L4_PATIENT_GROUNDED) > _index(
        current_level
    )
    crosses_l6 = target_level == EpistemicLevel.L6_CLINICALLY_ADJUDICATED and _index(
        current_level
    ) < _index(EpistemicLevel.L6_CLINICALLY_ADJUDICATED)

    allowed = True
    if crosses_l4:
        if has_grounding_evidence:
            reasons.append("L2/L3 -> L4+ crossing: grounding evidence present")
        else:
            reasons.append(
                "L2/L3 -> L4+ crossing blocked: no grounding evidence (6A.3: 'L2 ↛ L4 without grounding')"
            )
            allowed = False
    if crosses_l6:
        if has_clinician_adjudication:
            reasons.append("-> L6 crossing: clinician adjudication present")
        else:
            reasons.append(
                "-> L6 crossing blocked: no clinician adjudication (6A.3: 'L3 ↛ L6 without clinician adjudication')"
            )
            allowed = False

    if not crosses_l4 and not crosses_l6:
        reasons.append("promotion within the same evidence tier; no additional gate applies")

    return allowed, reasons


def promote_to_grounded_proposition(
    hypothesis: ConversationalHypothesis,
    *,
    target_level: EpistemicLevel,
    grounding_evidence: list[str],
    source_assertion_ids: list[uuid.UUID] | None = None,
    has_clinician_adjudication: bool = False,
) -> tuple[ConversationalHypothesis, GroundedProposition]:
    """Promote a ConversationalHypothesis into a GroundedProposition.

    Raises PromotionNotPermitted if the epistemic ladder rules aren't
    satisfied. On success, returns (updated_hypothesis, new_proposition):
    the hypothesis is not mutated in place (pydantic models here are
    treated as immutable-by-convention) -- the caller is responsible for
    persisting both.
    """
    allowed, reasons = can_promote(
        hypothesis.epistemic_level,
        target_level,
        has_grounding_evidence=bool(grounding_evidence),
        has_clinician_adjudication=has_clinician_adjudication,
    )
    if not allowed:
        raise PromotionNotPermitted(reasons)

    proposition = GroundedProposition(
        session_id=hypothesis.session_id,
        content=hypothesis.content,
        epistemic_level=target_level,
        grounding_evidence=grounding_evidence,
        source_assertion_ids=source_assertion_ids or [],
    )
    updated_hypothesis = hypothesis.model_copy(
        update={
            "status": HypothesisStatus.PROMOTED,
            "promoted_proposition_id": proposition.proposition_id,
        }
    )
    return updated_hypothesis, proposition
