"""Correction propagation (6A.4) and the repair-mandatory invariant
(6A.15), for the Model Layer objects in periop_core.model_layer.

Reference convention: an evidence/observation/support string that
references another Model Layer object uses the form "<kind>:<uuid>",
e.g. "proposition:3fa85f64-5717-4562-b3fc-2c963f66afa6" (build these with
`reference_string` so the convention is applied consistently). A plain
free-text evidence note such as "patient confirmed on direct
questioning" is not treated as a dependency on anything.

Scope honestly stated: `find_dependents` can only find dependents that
follow this reference-string convention. It does not do semantic/
NLP-based dependency detection -- that would require the (unbuilt) LLM
extraction layer. This is real, exact-match graph traversal over
whatever references were actually recorded, nothing more.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from periop_core.enums import Materiality, RepairStatus, RepairType
from periop_core.model_layer import (
    CausalHypothesis,
    ConversationalHypothesis,
    GroundedProposition,
    RepairRequirement,
)


def reference_string(kind: str, obj_id: uuid.UUID) -> str:
    return f"{kind}:{obj_id}"


@dataclass(frozen=True)
class DependentsResult:
    dependent_hypotheses: list[ConversationalHypothesis] = field(default_factory=list)
    dependent_propositions: list[GroundedProposition] = field(default_factory=list)
    dependent_causal_hypotheses: list[CausalHypothesis] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (
            self.dependent_hypotheses
            or self.dependent_propositions
            or self.dependent_causal_hypotheses
        )

    def total_count(self) -> int:
        return (
            len(self.dependent_hypotheses)
            + len(self.dependent_propositions)
            + len(self.dependent_causal_hypotheses)
        )


def find_dependents(
    superseded_reference: str,
    *,
    hypotheses: list[ConversationalHypothesis] = (),
    propositions: list[GroundedProposition] = (),
    causal_hypotheses: list[CausalHypothesis] = (),
) -> DependentsResult:
    return DependentsResult(
        dependent_hypotheses=[
            h for h in hypotheses if superseded_reference in h.supporting_observations
        ],
        dependent_propositions=[
            p for p in propositions if superseded_reference in p.grounding_evidence
        ],
        dependent_causal_hypotheses=[
            c for c in causal_hypotheses if superseded_reference in c.supporting_evidence
        ],
    )


def required_repair_for_correction(
    superseded_reference: str,
    dependents: DependentsResult,
    *,
    session_id: uuid.UUID,
    turn_id: uuid.UUID | None = None,
) -> RepairRequirement:
    """6A.4: 'A repaired fact must propagate through the assertion graph
    and invalidate stale downstream inference.' 6A.15: 'Repair is
    mandatory when material misunderstanding is detected.'

    A correction with no recorded dependents is still logged as a
    (low-materiality) repair requirement -- corrections are never silent,
    even when nothing downstream happened to depend on the corrected
    item.
    """
    materiality = Materiality.HIGH if not dependents.is_empty() else Materiality.LOW
    return RepairRequirement(
        session_id=session_id,
        turn_id=turn_id,
        repair_type=RepairType.FACTUAL_ACCURACY,
        description=(
            f"Correction of {superseded_reference} invalidates "
            f"{len(dependents.dependent_hypotheses)} hypothesis(es), "
            f"{len(dependents.dependent_propositions)} proposition(s) and "
            f"{len(dependents.dependent_causal_hypotheses)} causal hypothesis(es) "
            f"that cited it as evidence."
        ),
        materiality=materiality,
        status=RepairStatus.OPEN,
    )
