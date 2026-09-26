from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel

from periop_core.enums import AssertionState, Certainty, Speaker
from periop_core.models import (
    Conflict,
    InformationGap,
    OpenTask,
    PatientAgendaItem,
    RequirementState,
    Session,
    WorkingFact,
)
from periop_core.safety import ClosureOutcome


class CreateSessionRequest(BaseModel):
    subject_ref: str
    encounter_ref: str | None = None
    procedure_context: dict[str, Any] = {}

    age_years: int | None = None
    age_source: str = "self_declared"
    is_obstetric_procedure: bool | None = False
    is_obstetric_source: str = "self_declared"
    is_emergency_listing: bool | None = False
    is_emergency_source: str = "self_declared"


class SessionRejectedResponse(BaseModel):
    reasons: list[str]


class AddAssertionRequest(BaseModel):
    """Demo shortcut -- see periop_api/__init__.py docstring. In the real
    system this is never a direct client-facing endpoint; assertions come
    only from validated LLM extraction over a patient Turn."""

    concept_code: str  # Clinical Dataset Concept_ID, e.g. "ALL-003"
    concept_text: str | None = None  # defaults to the dataset's concept label
    value: Any | None = None
    assertion_state: AssertionState
    certainty: Certainty = Certainty.EXPLICIT
    source_type: str  # e.g. "PATIENT", "EMR", "PROXY"
    speaker: Speaker = Speaker.PATIENT


class GapWithLabel(BaseModel):
    gap: InformationGap
    requirement_id: str
    domain: str | None = None
    concept: str | None = None


class ClosurePreview(BaseModel):
    outcome: ClosureOutcome
    blocking_reasons: list[str]
    open_action_reasons: list[str]


class SessionSummary(BaseModel):
    session: Session
    working_facts: list[WorkingFact]
    conflicts: list[Conflict]
    requirement_states: list[RequirementState]
    gaps: list[GapWithLabel]
    tasks: list[OpenTask]
    agenda_items: list[PatientAgendaItem]
    closure_preview: ClosurePreview


class ConceptOption(BaseModel):
    concept_id: str
    domain: str
    concept: str
    patient_question: str
    requirement_class: str
