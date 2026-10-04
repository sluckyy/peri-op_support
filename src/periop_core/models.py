"""Canonical objects from the Full Project Specification v1.0, Table 27
(canonical object definitions) and Table 28 (relational schema reference).

These are the "deterministic core" data model — Phase 1 of Table 24
(Development and deployment plan). No LLM call has authority to construct
these directly (INV-013); they are created and mutated only by the
service layer in `periop_core.services`.

Where a table-level invariant from Table 20 can be enforced at the model
level (i.e. it only depends on the object's own fields), it is enforced
here with a pydantic validator and the invariant ID is cited in the
docstring/comment. Invariants that depend on *other* objects' state (e.g.
INV-006, INV-010) are enforced in the service layer instead — see
`periop_core.gap_engine` and `periop_core.reconciliation`.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from periop_core.enums import (
    ActionType,
    AgendaPriority,
    AgendaStatus,
    AssertionState,
    AuditEventType,
    Certainty,
    ConflictStatus,
    ConflictType,
    CueStatus,
    CueType,
    EligibilityResult,
    GapStatus,
    GapType,
    InformationState,
    InterviewActionStatus,
    Materiality,
    Modality,
    RequirementClass,
    ResolutionOption,
    Salience,
    SessionStatus,
    Speaker,
    TaskPriority,
    TaskStatus,
    TaskType,
    VerificationState,
)


def _uuid4() -> uuid.UUID:
    return uuid.uuid4()


class ConceptReference(BaseModel):
    """A coded/text clinical concept reference.

    TERM-001 (Terminology Normalisation): original patient wording is
    never replaced by a code/display — both are retained.
    """

    original_text: str
    code: str | None = None
    system: str | None = None
    display: str | None = None
    mapping_status: str | None = None  # EXACT|BROADER|NARROWER|AMBIGUOUS|UNMAPPED|LOCAL


class SourceReference(BaseModel):
    """Source metadata for an Assertion (source_json in Table 28)."""

    source_type: str  # e.g. PATIENT, PROXY, EMR, DEVICE, CLINICIAN, DOCUMENT
    speaker: Speaker
    source_id: str | None = None
    document_ref: str | None = None
    turn_id: uuid.UUID | None = None


class ReleaseManifest(BaseModel):
    """Table 27 / §12.2. Immutable for a session except via governed
    migration (INV-012)."""

    manifest_id: uuid.UUID = Field(default_factory=_uuid4)
    clinical_dataset_version: str
    rules_version: str
    terminology_version: str
    prompt_version: str
    extractor_model_id: str
    language_model_id: str
    validator_version: str
    fhir_mapping_version: str
    site_configuration_version: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"frozen": True}


class Session(BaseModel):
    """Table 27 / DDL `session`.

    Addendum additions (docs/addenda/v1.1-gap-remediation.md):
    - `notice_acknowledged_at` for INV-017 (AI-interaction notice).
    - `eligibility_result` for INV-018 (intake eligibility check).
    """

    session_id: uuid.UUID = Field(default_factory=_uuid4)
    subject_ref: str
    encounter_ref: str | None = None
    procedure_context: dict[str, Any] = Field(default_factory=dict)
    status: SessionStatus = SessionStatus.INITIALISE
    manifest_id: uuid.UUID
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Addendum #1 (INV-017)
    notice_acknowledged_at: datetime | None = None
    # Addendum #2 (INV-018)
    eligibility_result: EligibilityResult | None = None

    def has_ai_notice(self) -> bool:
        return self.notice_acknowledged_at is not None


class Assertion(BaseModel):
    """Table 27 / DDL `assertion`.

    INV-001: every Assertion has traceable source and provenance — enforced
    below (source is required; provenance dict must be non-empty).
    INV-013: only ever constructed by the service layer from a validated
    LLM extraction or a direct authoritative-source read, never delivered
    to a patient/clinician as clinical truth on its own.
    """

    assertion_id: uuid.UUID = Field(default_factory=_uuid4)
    session_id: uuid.UUID
    subject_ref: str
    concept: ConceptReference
    value: Any | None = None
    assertion_state: AssertionState
    source: SourceReference
    event_time: dict[str, Any] | None = None  # exact/range/approximate + raw phrase
    assertion_time: datetime = Field(default_factory=datetime.utcnow)
    certainty: Certainty
    provenance: dict[str, Any]
    supersedes_assertion_id: uuid.UUID | None = None

    @field_validator("provenance")
    @classmethod
    def _provenance_non_empty(cls, v: dict[str, Any]) -> dict[str, Any]:
        # INV-001
        if not v:
            raise ValueError(
                "INV-001 violation: Assertion.provenance must be non-empty "
                "(extractor/model/rule/source offsets are required)"
            )
        return v

    @model_validator(mode="after")
    def _cannot_supersede_self(self) -> "Assertion":
        if self.supersedes_assertion_id == self.assertion_id:
            raise ValueError("An assertion cannot supersede itself")
        return self


class WorkingFact(BaseModel):
    """Table 27 / DDL `working_fact`.

    INV-003: WorkingFact cannot exist without a supporting assertion —
    enforced below. The working fact never erases a dissenting assertion
    (§4.2); dissenting assertions are tracked, not discarded.
    """

    fact_id: uuid.UUID = Field(default_factory=_uuid4)
    session_id: uuid.UUID
    concept: ConceptReference
    value: Any | None = None
    verification_state: VerificationState
    freshness: dict[str, Any] | None = None
    version: int = 1
    supporting_assertion_ids: list[uuid.UUID]
    dissenting_assertion_ids: list[uuid.UUID] = Field(default_factory=list)

    @field_validator("supporting_assertion_ids")
    @classmethod
    def _at_least_one_supporting_assertion(
        cls, v: list[uuid.UUID]
    ) -> list[uuid.UUID]:
        # INV-003
        if not v:
            raise ValueError(
                "INV-003 violation: WorkingFact must have at least one "
                "supporting assertion"
            )
        return v


class Conflict(BaseModel):
    """Table 27 / DDL `conflict`.

    INV-004: a material (HIGH/CRITICAL) conflict remains visible until
    governed resolution — enforced in the reconciliation engine, not here
    (this model only records state; `can_auto_resolve` is advisory).
    """

    conflict_id: uuid.UUID = Field(default_factory=_uuid4)
    session_id: uuid.UUID
    assertion_ids: list[uuid.UUID]
    type: ConflictType
    materiality: Materiality
    status: ConflictStatus = ConflictStatus.OPEN
    resolution: dict[str, Any] | None = None

    @field_validator("assertion_ids")
    @classmethod
    def _conflict_needs_at_least_two_assertions(
        cls, v: list[uuid.UUID]
    ) -> list[uuid.UUID]:
        if len(v) < 2:
            raise ValueError(
                "A Conflict must reference at least two disagreeing assertions"
            )
        return v

    def can_auto_resolve(self) -> bool:
        """Reconciliation Algorithm step 6/7: HIGH/CRITICAL conflicts
        cannot auto-resolve except by an explicitly approved deterministic
        rule, which this generic model has no knowledge of — so the
        conservative answer for HIGH/CRITICAL is always False here."""
        return self.materiality in (Materiality.LOW, Materiality.MODERATE)


class Requirement(BaseModel):
    """Table 27 — the *definition* of a clinical information obligation
    (versioned, from the Clinical Dataset). Distinct from RequirementState,
    which is the per-session instance of it."""

    requirement_id: str  # Concept_ID, e.g. "CARD-014"
    activation_rule: str  # e.g. "All patients" / a trigger expression
    requiredness: RequirementClass
    minimum_state: InformationState = InformationState.KNOWN_CONFIRMED
    freshness_rule: dict[str, Any] | None = None


class RequirementState(BaseModel):
    """Table 27 / DDL `requirement_state`.

    INV-005: NOT_ASKED, UNKNOWN, DECLINED and a negated/confirmed-absent
    state are distinct and must never collapse into each other — enforced
    by using the InformationState enum itself (no separate boolean/None
    "resolved" flag exists to be misused).
    """

    requirement_state_id: uuid.UUID = Field(default_factory=_uuid4)
    session_id: uuid.UUID
    requirement_id: str
    information_state: InformationState
    evidence_refs: list[uuid.UUID] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)


class InformationGap(BaseModel):
    """Table 27 / DDL `information_gap`.

    INV-006 (NOT_APPLICABLE requirement cannot generate an active gap) is
    enforced by the factory function in `periop_core.gap_engine`, not
    here, because it depends on the parent RequirementState's
    information_state.
    """

    gap_id: uuid.UUID = Field(default_factory=_uuid4)
    requirement_state_id: uuid.UUID
    gap_type: GapType
    priority_score: float
    status: GapStatus = GapStatus.OPEN
    resolution_options: list[ResolutionOption] = Field(default_factory=list)


class InterviewAction(BaseModel):
    """Table 27 / DDL `interview_action`.

    INV-007: must exist before LLM patient-facing generation — enforced by
    the orchestrator/API boundary (out of scope for Phase 1; see
    `periop_core.services`), not this model.
    """

    action_id: uuid.UUID = Field(default_factory=_uuid4)
    session_id: uuid.UUID
    action_type: ActionType
    targets: list[str] = Field(default_factory=list)  # gap_id/requirement_id strings
    purpose: str
    permitted_content: list[str] = Field(default_factory=list)
    prohibited_content: list[str] = Field(default_factory=list)
    max_questions: int = 1
    fallback: str | None = None
    status: InterviewActionStatus = InterviewActionStatus.SELECTED


class Turn(BaseModel):
    """Table 27 / DDL `turn`.

    INV-008: delivered agent Turn references exact approved content/action
    — enforced by the language/validator service, not this model.
    """

    turn_id: uuid.UUID = Field(default_factory=_uuid4)
    session_id: uuid.UUID
    action_id: uuid.UUID | None = None
    speaker: Speaker
    modality: Modality
    content: str
    confidence: float | None = None
    occurred_at: datetime = Field(default_factory=datetime.utcnow)


class OpenTask(BaseModel):
    """Table 27 (named `OpenAction` there) / DDL `task`.

    INV-010: a critical Task must have an explicit owner before closure —
    enforced by the closure gate (service layer), not this model, since a
    critical task is legitimately unowned for a time after creation.
    """

    task_id: uuid.UUID = Field(default_factory=_uuid4)
    session_id: uuid.UUID
    type: TaskType
    priority: TaskPriority
    reason: dict[str, Any]
    owner_ref: str | None = None
    status: TaskStatus = TaskStatus.OPEN

    def blocks_closure(self) -> bool:
        return self.priority == TaskPriority.CRITICAL and self.owner_ref is None


class Cue(BaseModel):
    """Table 27 / DDL `cue`."""

    cue_id: uuid.UUID = Field(default_factory=_uuid4)
    session_id: uuid.UUID
    turn_id: uuid.UUID
    cue_type: CueType
    salience: Salience
    status: CueStatus = CueStatus.OPEN


class PatientAgendaItem(BaseModel):
    """Table 27 / DDL `patient_agenda_item`.

    INV-014 (non-critical): a high-priority patient agenda item needs
    disposition before closure — enforced by the closure gate.
    """

    agenda_item_id: uuid.UUID = Field(default_factory=_uuid4)
    session_id: uuid.UUID
    text: str
    priority: AgendaPriority
    status: AgendaStatus = AgendaStatus.OPEN
    source_turn_id: uuid.UUID | None = None


class AuditEvent(BaseModel):
    """SVC-014 (Audit & Provenance Service): one entry in a session's
    immutable lineage. `entity_type`/`entity_id` identify what the event
    is about (e.g. "assertion"/an Assertion's id); `payload` carries
    whatever's needed to reconstruct that mutation without re-deriving it
    from other tables. See periop_core.audit_db for append/read and
    db/migrations/0003_audit_trail.sql for how immutability is enforced.
    """

    event_id: uuid.UUID = Field(default_factory=_uuid4)
    session_id: uuid.UUID
    event_type: AuditEventType
    entity_type: str
    entity_id: uuid.UUID | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=datetime.utcnow)
