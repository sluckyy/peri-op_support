"""Psychological safety estimation (Full Spec §6A.7).

    PSt = P(interpersonal risk can be taken safely | observations_0:t)

Scope honestly stated -- read this before using `estimate` for anything:
this is a small, fully deterministic, named-signal heuristic, not a
validated psychological or clinical measure and not a learned model. It
exists so the Model Layer has *some* bounded, auditable, testable
representation of this state for MVP purposes, per Table 13 ("Required,
conservative"). The signal names and deltas below are a reasonable
starting point grounded in the spec's own prose (6A.7's bullet list) but
have not been calibrated against real conversations. Treat the resulting
`estimate` as a rough, inspectable heuristic signal for conversational
policy -- e.g. whether to use more INVITE_CORRECTION/NORMALISE actions --
never as a clinical or psychological assessment of the patient.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from periop_core.model_layer import PsychologicalSafetyState

# Grounded in 6A.7's own bullet list: humility/uncertainty admission,
# acknowledging errors, normalisation, and genuine ability to decline are
# all framed as things that should make disagreement/correction/
# disclosure feel safer; unacknowledged system error and visible distress
# when correcting the system are the converse.
SIGNAL_DELTAS: dict[str, float] = {
    "patient_corrected_system_without_hesitation": 0.08,
    "patient_disclosed_sensitive_information": 0.06,
    "patient_asked_a_question": 0.04,
    "patient_declined_to_answer_calmly": 0.03,
    "patient_admitted_uncertainty_or_nonadherence": 0.05,
    "system_acknowledged_its_own_error": 0.03,
    "patient_showed_distress_when_correcting_system": -0.10,
    "patient_gave_minimal_deflecting_answers": -0.05,
    "system_error_went_unacknowledged": -0.08,
}

INITIAL_ESTIMATE = 0.5  # neutral prior; not itself a claim about the patient


def initial_state(session_id: uuid.UUID) -> PsychologicalSafetyState:
    return PsychologicalSafetyState(
        session_id=session_id,
        estimate=INITIAL_ESTIMATE,
        evidence_signals=["initial neutral prior, no observations yet"],
    )


def update(
    current: PsychologicalSafetyState, signal_names: list[str]
) -> PsychologicalSafetyState:
    """Apply one or more named signals (see SIGNAL_DELTAS) and return a
    new, bounded PsychologicalSafetyState. Raises KeyError for an unknown
    signal name rather than silently ignoring it -- a typo here should
    fail loud, not quietly do nothing."""
    if not signal_names:
        return current

    delta = 0.0
    for name in signal_names:
        if name not in SIGNAL_DELTAS:
            raise KeyError(
                f"Unknown psychological-safety signal {name!r}; known signals: "
                f"{sorted(SIGNAL_DELTAS)}"
            )
        delta += SIGNAL_DELTAS[name]

    new_estimate = min(1.0, max(0.0, current.estimate + delta))
    return current.model_copy(
        update={
            "estimate": new_estimate,
            "evidence_signals": [*current.evidence_signals, *signal_names],
            "updated_at": datetime.utcnow(),
        }
    )
