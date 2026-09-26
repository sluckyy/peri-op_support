"""Enumerations from the Full Project Specification v1.0.

Each enum cites the spec table it was transcribed from so drift between
code and spec is easy to spot in review. See
docs/exports/full_project_specification_v1.0.md for the source tables.
"""
from __future__ import annotations

from enum import Enum


class InformationState(str, Enum):
    """Table 5 — the 12-state information-state taxonomy.

    Safety invariant (Table 6): none of these may be silently converted
    into another. In particular UNKNOWN, NOT_ASKED, DECLINED, UNAVAILABLE,
    NOT_APPLICABLE and an explicit negative are all distinct.
    """

    KNOWN_CONFIRMED = "KNOWN_CONFIRMED"
    KNOWN_UNCONFIRMED = "KNOWN_UNCONFIRMED"
    PARTIAL = "PARTIAL"
    STALE = "STALE"
    CONFLICTING = "CONFLICTING"
    UNKNOWN = "UNKNOWN"
    NOT_ASKED = "NOT_ASKED"
    DECLINED = "DECLINED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNAVAILABLE = "UNAVAILABLE"
    DEFERRED = "DEFERRED"
    SAFETY_ESCALATED = "SAFETY_ESCALATED"


class AssertionState(str, Enum):
    """DDL Table 28, `assertion.assertion_state`."""

    AFFIRMED = "AFFIRMED"
    NEGATED = "NEGATED"
    UNCERTAIN = "UNCERTAIN"
    UNKNOWN = "UNKNOWN"
    DECLINED = "DECLINED"
    CONDITIONAL = "CONDITIONAL"


class Certainty(str, Enum):
    """DDL Table 28, `assertion.certainty`.

    Never inflated during FHIR projection (INV-011) or terminology mapping.
    """

    EXPLICIT = "EXPLICIT"
    INFERRED_LOW = "INFERRED_LOW"
    INFERRED_MODERATE = "INFERRED_MODERATE"
    UNRESOLVED = "UNRESOLVED"


class VerificationState(str, Enum):
    """DDL Table 28, `working_fact.verification_state`."""

    CONFIRMED = "CONFIRMED"
    UNCONFIRMED = "UNCONFIRMED"
    CONFLICTED = "CONFLICTED"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class ConflictType(str, Enum):
    """DDL Table 28, `conflict.type`; narrative definitions in §4.3."""

    VALUE = "VALUE"
    NEGATION = "NEGATION"
    TEMPORAL = "TEMPORAL"
    IDENTITY = "IDENTITY"
    TERMINOLOGY = "TERMINOLOGY"
    SOURCE = "SOURCE"
    PROCEDURE = "PROCEDURE"


class Materiality(str, Enum):
    """DDL Table 28, `conflict.materiality`.

    HIGH/CRITICAL conflicts cannot be silently auto-resolved except by an
    explicitly approved deterministic rule (§4.3).
    """

    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ConflictStatus(str, Enum):
    """DDL Table 28, `conflict.status`."""

    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    ACCEPTED_RISK = "ACCEPTED_RISK"


class SessionStatus(str, Enum):
    """DDL Table 28, `session.status`."""

    INITIALISE = "INITIALISE"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETE = "COMPLETE"
    HANDOFF = "HANDOFF"
    STOPPED = "STOPPED"


class RequirementClass(str, Enum):
    """Clinical Dataset `Requirement_class` column; defined in Data Dictionary.

    M0 universal mandatory; M1 mandatory where applicable; C1 condition-
    triggered; C2 procedure-triggered; C3 medication-triggered; C4 risk/
    demographic-triggered; O optional/contextual.
    """

    M0 = "M0"
    M1 = "M1"
    C1 = "C1"
    C2 = "C2"
    C3 = "C3"
    C4 = "C4"
    O = "O"


class GapType(str, Enum):
    """§5.1 — gap types."""

    MISSING = "MISSING"
    PARTIAL = "PARTIAL"
    STALE = "STALE"
    UNVERIFIED = "UNVERIFIED"
    CONFLICTING = "CONFLICTING"
    UNAVAILABLE_SOURCE = "UNAVAILABLE_SOURCE"
    DEFERRED = "DEFERRED"
    SAFETY_ESCALATED = "SAFETY_ESCALATED"


class GapStatus(str, Enum):
    """DDL Table 28, `information_gap.status`."""

    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    DEFERRED = "DEFERRED"
    HANDOFF = "HANDOFF"


class ResolutionOption(str, Enum):
    """§5.2 — ask/confirm/suppress/retrieve/handoff logic."""

    SUPPRESS = "SUPPRESS"
    CONFIRM = "CONFIRM"
    ASK = "ASK"
    RETRIEVE = "RETRIEVE"
    HANDOFF = "HANDOFF"


class ActionType(str, Enum):
    """Table 7 — the full InterviewAction vocabulary."""

    OPEN_INVITATION = "OPEN_INVITATION"
    FACILITATE = "FACILITATE"
    REFLECT = "REFLECT"
    SUMMARISE = "SUMMARISE"
    AGENDA_SOLICIT = "AGENDA_SOLICIT"
    SIGNPOST = "SIGNPOST"
    FOCUSED_PROBE = "FOCUSED_PROBE"
    CLOSED_SCREEN = "CLOSED_SCREEN"
    CONFIRM = "CONFIRM"
    CLARIFY = "CLARIFY"
    EXPLAIN_REASON = "EXPLAIN_REASON"
    REQUEST_SOURCE = "REQUEST_SOURCE"
    CREATE_TASK = "CREATE_TASK"
    INTERRUPT_FOR_SAFETY = "INTERRUPT_FOR_SAFETY"
    HANDOFF = "HANDOFF"
    RETURN_TO_TOPIC = "RETURN_TO_TOPIC"
    FINAL_OPEN = "FINAL_OPEN"
    TEACH_BACK = "TEACH_BACK"


class InterviewActionStatus(str, Enum):
    """DDL Table 28, `interview_action.status`."""

    SELECTED = "SELECTED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


class Speaker(str, Enum):
    """DDL Table 28, `turn.speaker`."""

    PATIENT = "PATIENT"
    AGENT = "AGENT"
    CLINICIAN = "CLINICIAN"
    PROXY = "PROXY"
    SYSTEM = "SYSTEM"


class Modality(str, Enum):
    """DDL Table 28, `turn.modality`."""

    TEXT = "TEXT"
    VOICE = "VOICE"
    ASSISTED = "ASSISTED"


class TaskType(str, Enum):
    """DDL Table 28, `task.type`."""

    RETRIEVAL = "RETRIEVAL"
    CLINICAL_REVIEW = "CLINICAL_REVIEW"
    SAFETY = "SAFETY"
    IDENTITY = "IDENTITY"
    PROCEDURE = "PROCEDURE"
    OTHER = "OTHER"


class TaskPriority(str, Enum):
    """DDL Table 28, `task.priority`."""

    ROUTINE = "ROUTINE"
    URGENT = "URGENT"
    CRITICAL = "CRITICAL"


class TaskStatus(str, Enum):
    """DDL Table 28, `task.status`."""

    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"


class CueType(str, Enum):
    """DDL Table 28, `cue.cue_type`."""

    CLINICAL = "CLINICAL"
    EMOTIONAL = "EMOTIONAL"
    COMMUNICATION = "COMMUNICATION"
    SAFETY = "SAFETY"


class Salience(str, Enum):
    """DDL Table 28, `cue.salience`."""

    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CueStatus(str, Enum):
    """DDL Table 28, `cue.status`."""

    OPEN = "OPEN"
    ADDRESSED = "ADDRESSED"
    ESCALATED = "ESCALATED"


class AgendaPriority(str, Enum):
    """DDL Table 28, `patient_agenda_item.priority`."""

    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"


class AgendaStatus(str, Enum):
    """DDL Table 28, `patient_agenda_item.status`."""

    OPEN = "OPEN"
    ADDRESSED = "ADDRESSED"
    DEFERRED = "DEFERRED"
    HANDOFF = "HANDOFF"


class FactAssertionRole(str, Enum):
    """DDL Table 28, `fact_assertion_link.role`."""

    SUPPORTS = "SUPPORTS"
    DISSENTS = "DISSENTS"
    SUPERSEDES = "SUPERSEDES"


class EligibilityResult(str, Enum):
    """Addendum item 2 — new intake eligibility check, not in v1.0.

    See docs/addenda/v1.1-gap-remediation.md #2.
    """

    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
