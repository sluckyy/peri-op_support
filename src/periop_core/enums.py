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
    """Table 7 — the full InterviewAction vocabulary, plus Table 12's
    Model Layer additions (v1.1 §6A.12) appended below the original set.

    AFFILIATIVE_HUMOUR is feature-flagged off by default (Table 13) — see
    periop_core.humour_policy. It exists in the vocabulary so a governed
    action contract can name it, not so it fires by default.
    """

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

    # -- Table 12 (v1.1 §6A.12): Model Layer additions --
    WAIT = "WAIT"
    BACKCHANNEL = "BACKCHANNEL"
    ACKNOWLEDGE = "ACKNOWLEDGE"
    NORMALISE = "NORMALISE"
    VALIDATE_EXPERIENCE = "VALIDATE_EXPERIENCE"
    INVITE_CORRECTION = "INVITE_CORRECTION"
    ACKNOWLEDGE_LIMITATION = "ACKNOWLEDGE_LIMITATION"
    ACKNOWLEDGE_ERROR = "ACKNOWLEDGE_ERROR"
    AFFILIATIVE_HUMOUR = "AFFILIATIVE_HUMOUR"
    DEFER_WITH_OBLIGATION = "DEFER_WITH_OBLIGATION"


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


# ============================================================
# v1.1 Model Layer (§6A) — see
# docs/exports/full_project_specification_v1.1_model_layer.md
# ============================================================


class EpistemicLevel(str, Enum):
    """Table 10 — the epistemic ladder (6A.3). Promotion is monotonic and
    only permitted when the required evidence exists — see
    periop_core.epistemic.can_promote(). A level here is a property of a
    single proposition's grounding, distinct from InformationState (which
    describes whether a *clinical requirement* has been satisfied) and
    from AssertionState/Certainty (which describe a single sourced
    statement). All three coexist deliberately per the Model Layer's own
    layering: L0-L1 concern raw/literal interpretation of an utterance,
    L2-L3 concern conversational hypotheses, L4-L6 concern how firmly a
    proposition may be treated as clinically grounded truth.
    """

    L0_RAW_UTTERANCE = "L0_RAW_UTTERANCE"
    L1_LITERAL_INTERPRETATION = "L1_LITERAL_INTERPRETATION"
    L2_PRAGMATIC_INTERPRETATION = "L2_PRAGMATIC_INTERPRETATION"
    L3_CLINICAL_HYPOTHESIS = "L3_CLINICAL_HYPOTHESIS"
    L4_PATIENT_GROUNDED = "L4_PATIENT_GROUNDED"
    L5_EXTERNALLY_VERIFIED = "L5_EXTERNALLY_VERIFIED"
    L6_CLINICALLY_ADJUDICATED = "L6_CLINICALLY_ADJUDICATED"


# Ordering used by periop_core.epistemic to detect a "jump" promotion.
EPISTEMIC_LEVEL_ORDER: tuple[EpistemicLevel, ...] = (
    EpistemicLevel.L0_RAW_UTTERANCE,
    EpistemicLevel.L1_LITERAL_INTERPRETATION,
    EpistemicLevel.L2_PRAGMATIC_INTERPRETATION,
    EpistemicLevel.L3_CLINICAL_HYPOTHESIS,
    EpistemicLevel.L4_PATIENT_GROUNDED,
    EpistemicLevel.L5_EXTERNALLY_VERIFIED,
    EpistemicLevel.L6_CLINICALLY_ADJUDICATED,
)


class RepairType(str, Enum):
    """6A.4 — the kinds of conversational problem the Model Layer must be
    able to detect and represent."""

    RECOGNITION = "RECOGNITION"
    REFERENCE = "REFERENCE"
    SEMANTICS = "SEMANTICS"
    TEMPORALITY = "TEMPORALITY"
    FACTUAL_ACCURACY = "FACTUAL_ACCURACY"
    INTERPRETATION = "INTERPRETATION"
    CONTRADICTION = "CONTRADICTION"
    SCOPE = "SCOPE"
    PRAGMATICS = "PRAGMATICS"
    INTERRUPTION = "INTERRUPTION"
    EMOTIONAL_MISATTUNEMENT = "EMOTIONAL_MISATTUNEMENT"


class RepairStatus(str, Enum):
    """6A.15: 'Repair is mandatory when material misunderstanding is
    detected' — a RepairRequirement must remain OPEN until REPAIRED,
    DEFERRED (with a reason and, if still relevant, an obligation per
    6A.15), or HANDED_OFF. It cannot silently disappear."""

    OPEN = "OPEN"
    REPAIRED = "REPAIRED"
    DEFERRED = "DEFERRED"
    HANDED_OFF = "HANDED_OFF"


class HypothesisStatus(str, Enum):
    """Status of a ConversationalHypothesis or CausalHypothesis. Mirrors
    the epistemic-ladder spirit: a hypothesis stays a hypothesis (Table 9:
    'cannot be projected as fact') until explicitly promoted/adjudicated
    or explicitly retracted by a correction."""

    ACTIVE = "ACTIVE"
    PROMOTED = "PROMOTED"
    RETRACTED = "RETRACTED"
    SUPERSEDED = "SUPERSEDED"


class CausalRelationStatus(str, Enum):
    """CausalHypothesis.status (Table 9 / 6A.10). Chronology, association
    and causation are kept as distinct relations — see
    periop_core.causal_reasoning."""

    HYPOTHESIS = "HYPOTHESIS"
    DISCRIMINATED = "DISCRIMINATED"  # a discriminating question was asked
    ADJUDICATED = "ADJUDICATED"  # clinician-owned judgement reached
    RETRACTED = "RETRACTED"


class ObligationStatus(str, Enum):
    """ProspectiveObligation.status (Table 9 / 6A.5). 6A.15: 'Deferral
    creates an obligation when the issue remains relevant' — an
    obligation must not simply be forgotten, so RESOLVED/HANDED_OFF are
    the only terminal states; there is no silent "expired" state."""

    PENDING = "PENDING"
    DUE = "DUE"
    RESOLVED = "RESOLVED"
    HANDED_OFF = "HANDED_OFF"


class ContradictionStatus(str, Enum):
    """Contradiction.status (Table 9). Distinct from the Clinical State
    layer's ConflictStatus — see periop_core.model_layer module docstring
    for how a conversation-level Contradiction relates to a Clinical
    State Conflict."""

    OPEN = "OPEN"
    RECONCILED = "RECONCILED"
    ESCALATED = "ESCALATED"


class AuditEventType(str, Enum):
    """AuditEvent.event_type (SVC-014). Covers the Phase 1 core
    session/assertion lifecycle and the v1.1 Model Layer (§6A) mutations
    -- see periop_core.audit_db and README "What's implemented" for what
    else still isn't wired in (e.g. Table 17's real Turn-submission
    events, which need the Phase 2 orchestrator)."""

    SESSION_CREATED = "SESSION_CREATED"
    NOTICE_ACKNOWLEDGED = "NOTICE_ACKNOWLEDGED"
    SESSION_ACTIVATED = "SESSION_ACTIVATED"
    ASSERTION_ADDED = "ASSERTION_ADDED"
    SESSION_CLOSED = "SESSION_CLOSED"

    HYPOTHESIS_CREATED = "HYPOTHESIS_CREATED"
    HYPOTHESIS_PROMOTED = "HYPOTHESIS_PROMOTED"
    PROPOSITION_CORRECTED = "PROPOSITION_CORRECTED"
    OBLIGATION_CREATED = "OBLIGATION_CREATED"
    CONTRADICTION_LOGGED = "CONTRADICTION_LOGGED"
    UNCERTAINTY_LOGGED = "UNCERTAINTY_LOGGED"
    REPAIR_CREATED = "REPAIR_CREATED"
    REPAIR_RESOLVED = "REPAIR_RESOLVED"
    PSYCHOLOGICAL_SAFETY_SIGNAL_APPLIED = "PSYCHOLOGICAL_SAFETY_SIGNAL_APPLIED"
    CAUSAL_HYPOTHESIS_CREATED = "CAUSAL_HYPOTHESIS_CREATED"
    CAUSAL_HYPOTHESIS_STATUS_CHANGED = "CAUSAL_HYPOTHESIS_STATUS_CHANGED"
    CONFLICT_REVIEW_CREATED = "CONFLICT_REVIEW_CREATED"
    CONFLICT_REVIEW_RESOLVED = "CONFLICT_REVIEW_RESOLVED"
