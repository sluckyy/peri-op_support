"""Humour policy gate (Full Spec §6A.8).

'Appropriate affiliative humour may be used as a bounded rapport and
psychological-safety action... It is never required and must not compete
with clinical safety, distress recognition or patient dignity.'

Table 13 marks affiliative humour "Feature-flagged; off by default until
evaluated" -- `HumourContext.feature_enabled` defaults to False for
exactly that reason. This module is a hard permission gate: even when a
utility score (see `humour_utility`) would be positive, `is_humour_permitted`
must pass before AFFILIATIVE_HUMOUR may be used as an action class.
"""
from __future__ import annotations

from dataclasses import dataclass

TargetKind = str  # "self" | "situation" | "patient"


@dataclass(frozen=True)
class HumourContext:
    feature_enabled: bool = False  # Table 13: off by default until evaluated
    proposed_target: TargetKind = "self"
    high_distress: bool = False
    serious_safety_disclosure_active: bool = False
    conflict_present: bool = False
    bereavement_context: bool = False
    receptivity_known: bool = False  # 6A.8: uncertain receptivity suppresses humour
    implies_incompetence: bool = False  # guards the self-deprecation rule


def is_humour_permitted(ctx: HumourContext) -> tuple[bool, list[str]]:
    """Returns (permitted, reasons). The first triggered suppression
    condition determines the result -- all applicable reasons are
    still listed for auditability."""
    reasons: list[str] = []

    if not ctx.feature_enabled:
        reasons.append("feature disabled (Table 13: off by default until evaluated)")

    if ctx.proposed_target == "patient":
        reasons.append(
            "patient-directed humour about mistakes/literacy/behaviour/symptoms/"
            "disclosure is prohibited outright (6A.8)"
        )

    if ctx.high_distress:
        reasons.append("suppressed: high distress")
    if ctx.serious_safety_disclosure_active:
        reasons.append("suppressed: serious safety disclosure in progress")
    if ctx.conflict_present:
        reasons.append("suppressed: conflict present")
    if ctx.bereavement_context:
        reasons.append("suppressed: bereavement context")
    if not ctx.receptivity_known:
        reasons.append("suppressed: receptivity uncertain (6A.8 conservative default)")
    if ctx.implies_incompetence:
        reasons.append(
            "suppressed: self-deprecation must not falsely imply incompetence or "
            "undermine clinical authority (6A.8)"
        )

    if reasons:
        return False, reasons
    return True, ["no suppression condition triggered and feature enabled"]


@dataclass(frozen=True)
class HumourUtilityFactors:
    """U(H) = Rapport + Affiliation + TensionReduction + StatusReduction
    - Misinterpretation - Inappropriateness - CompetenceLoss (6A.8).

    Advisory only -- see module docstring. Never consulted unless
    `is_humour_permitted` has already returned True.
    """

    rapport: float = 0.0
    affiliation: float = 0.0
    tension_reduction: float = 0.0
    status_reduction: float = 0.0
    misinterpretation_risk: float = 0.0
    inappropriateness_risk: float = 0.0
    competence_loss_risk: float = 0.0


def humour_utility(factors: HumourUtilityFactors) -> float:
    return (
        factors.rapport
        + factors.affiliation
        + factors.tension_reduction
        + factors.status_reduction
        - factors.misinterpretation_risk
        - factors.inappropriateness_risk
        - factors.competence_loss_risk
    )
