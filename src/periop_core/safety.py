"""Closure gate (Table 23 step 16; INV-004/010/014; v1.1 §6A.15).

Scope honestly stated: this module implements the *closure gate* only --
the deterministic check of whether a session may move to COMPLETE,
COMPLETE_WITH_OPEN_ACTIONS, or must remain blocked. It does NOT implement
red-flag rule *evaluation* (the Clinical Dataset's `Red_flag_rule` column
is prose, e.g. "Active or worsening symptoms require clinician review",
not yet a structured/executable predicate -- turning it into one is a
separate, larger piece of work: a rules-authoring format plus a compiler,
not something to fake here with string matching). Escalation classes
(ESC-001..012) and the safety-interrupt policy hierarchy (§7.1) are also
not implemented; they require the conversation orchestrator, which is out
of Phase 1 scope per Table 24.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from periop_core.models import Conflict, ConflictReview, OpenTask, PatientAgendaItem
from periop_core.model_layer import RepairRequirement
from periop_core.enums import (
    AgendaPriority,
    AgendaStatus,
    ConflictStatus,
    ContradictionStatus,
    Materiality,
    RepairStatus,
    TaskStatus,
)
from periop_core.reconciliation import CRITICAL_CONCEPT_PREFIXES


class ClosureOutcome(str, Enum):
    COMPLETE = "COMPLETE"
    COMPLETE_WITH_OPEN_ACTIONS = "COMPLETE_WITH_OPEN_ACTIONS"
    BLOCKED = "BLOCKED"


@dataclass
class ClosureResult:
    outcome: ClosureOutcome
    blocking_reasons: list[str] = field(default_factory=list)
    open_action_reasons: list[str] = field(default_factory=list)


def _is_critical_concept(code: str | None, original_text: str) -> bool:
    key = code or original_text.strip().lower()
    return any(key.startswith(p) for p in CRITICAL_CONCEPT_PREFIXES)


def evaluate_closure(
    open_tasks: list[OpenTask],
    agenda_items: list[PatientAgendaItem],
    conflicts: list[Conflict],
    repair_requirements: list[RepairRequirement] = (),
    conflict_reviews: list[ConflictReview] = (),
) -> ClosureResult:
    """INV-010: a critical unowned task blocks completion outright.
    INV-014 (non-critical) and open conflicts/tasks otherwise downgrade a
    would-be COMPLETE to COMPLETE_WITH_OPEN_ACTIONS rather than blocking.

    v1.1 §6A.15 ('repair is mandatory when material misunderstanding is
    detected'): an OPEN RepairRequirement of CRITICAL materiality blocks
    closure the same way an unowned critical Task does -- a session
    should not close over an unresolved, safety-relevant conversational
    misunderstanding. HIGH/MODERATE/LOW-materiality open repairs
    downgrade to COMPLETE_WITH_OPEN_ACTIONS, matching how conflicts are
    handled. `repair_requirements` defaults to `()` so existing callers
    that don't yet track them are unaffected.

    A ConflictReview that isn't RECONCILED (still OPEN, or ESCALATED --
    both mean nobody has actually decided which side is correct yet) on
    one of the identity/procedure/allergy/airway/anticoagulant-adjacent
    concepts (see `periop_core.reconciliation.CRITICAL_CONCEPT_PREFIXES`
    and §4.3) blocks closure the same way: logging the disagreement
    isn't enough on its own if nobody ever acts on it. Anything else
    unresolved downgrades to COMPLETE_WITH_OPEN_ACTIONS, matching how
    plain Conflicts are handled below. `conflict_reviews` defaults to
    `()` so existing callers that don't yet track them are unaffected.
    """
    blocking_reasons: list[str] = []
    open_action_reasons: list[str] = []

    for task in open_tasks:
        if task.blocks_closure():
            blocking_reasons.append(
                f"Critical task {task.task_id} has no owner (INV-010)"
            )
        elif task.status not in (TaskStatus.RESOLVED, TaskStatus.CANCELLED):
            open_action_reasons.append(f"Task {task.task_id} still {task.status.value}")

    for conflict in conflicts:
        if conflict.status == ConflictStatus.OPEN:
            open_action_reasons.append(
                f"Conflict {conflict.conflict_id} ({conflict.materiality.value}) still OPEN"
            )

    for item in agenda_items:
        if item.priority == AgendaPriority.HIGH and item.status in (
            AgendaStatus.OPEN,
            AgendaStatus.DEFERRED,
        ):
            open_action_reasons.append(
                f"High-priority patient agenda item {item.agenda_item_id} "
                f"still {item.status.value} (INV-014)"
            )

    for repair in repair_requirements:
        if repair.status != RepairStatus.OPEN:
            continue
        if repair.materiality == Materiality.CRITICAL:
            blocking_reasons.append(
                f"Critical unresolved repair requirement {repair.repair_id} "
                f"({repair.repair_type.value}) still OPEN (v1.1 §6A.15)"
            )
        else:
            open_action_reasons.append(
                f"Repair requirement {repair.repair_id} ({repair.materiality.value}) still OPEN"
            )

    for review in conflict_reviews:
        if review.status == ContradictionStatus.RECONCILED:
            continue
        label = review.concept.code or review.concept.original_text
        if _is_critical_concept(review.concept.code, review.concept.original_text):
            blocking_reasons.append(
                f"Critical conflict review {review.review_id} ({label}) still "
                f"{review.status.value} -- a clinician must resolve this "
                f"disagreement before closure (§4.3)"
            )
        else:
            open_action_reasons.append(
                f"Conflict review {review.review_id} ({label}) still {review.status.value}"
            )

    if blocking_reasons:
        return ClosureResult(ClosureOutcome.BLOCKED, blocking_reasons, open_action_reasons)
    if open_action_reasons:
        return ClosureResult(
            ClosureOutcome.COMPLETE_WITH_OPEN_ACTIONS, [], open_action_reasons
        )
    return ClosureResult(ClosureOutcome.COMPLETE, [], [])
