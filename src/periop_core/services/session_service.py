"""SVC-002 (Session Service), covering Table 23 steps 1-2 plus the new
step 1.5 (eligibility, addendum gap #2) and step for the INV-017 AI-role
notice (addendum gap #1).

`create_session` raises SessionCreationRejected rather than returning an
INITIALISE session for an ineligible subject — INV-018 ("Session cannot
leave INITIALISE for a subject outside the configured eligibility
boundary ... without an explicit governance override") is enforced by
never constructing the Session object at all in that case, which is a
stricter reading of the invariant than "construct it but mark it
rejected", and matches the addendum's "reject session creation with a
staff-contact message" behaviour.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from periop_core.eligibility import EligibilityContext, evaluate_eligibility
from periop_core.enums import EligibilityResult, SessionStatus
from periop_core.models import ReleaseManifest, Session


class SessionCreationRejected(Exception):
    """Raised when intake eligibility fails. `reasons` is patient/staff-
    facing safe (no clinical content, just the eligibility reasons) and
    should be surfaced as the addendum's "staff-contact message"."""

    def __init__(self, reasons: list[str]):
        super().__init__("; ".join(reasons))
        self.reasons = reasons


def create_session(
    subject_ref: str,
    manifest: ReleaseManifest,
    eligibility_ctx: EligibilityContext,
    encounter_ref: str | None = None,
    procedure_context: dict | None = None,
) -> Session:
    decision = evaluate_eligibility(eligibility_ctx)
    if decision.result is EligibilityResult.INELIGIBLE:
        raise SessionCreationRejected(decision.reasons)

    return Session(
        session_id=uuid.uuid4(),
        subject_ref=subject_ref,
        encounter_ref=encounter_ref,
        procedure_context=procedure_context or {},
        status=SessionStatus.INITIALISE,
        manifest_id=manifest.manifest_id,
        eligibility_result=decision.result,
    )


def acknowledge_ai_notice(session: Session) -> Session:
    """INV-017: patient must be shown the AI-role/data-use notice before
    the first clinical question. This is the logging of that event; the
    Experience-layer enforcement that no clinical InterviewAction can be
    realised before this is set belongs to the (unbuilt) orchestrator.
    """
    return session.model_copy(update={"notice_acknowledged_at": datetime.utcnow()})


def activate_session(session: Session) -> Session:
    if not session.has_ai_notice():
        raise ValueError(
            "INV-017 violation: cannot activate a session before the "
            "AI-role/data-use notice has been acknowledged"
        )
    if session.status is not SessionStatus.INITIALISE:
        raise ValueError(f"Cannot activate a session in status {session.status}")
    return session.model_copy(update={"status": SessionStatus.ACTIVE})
