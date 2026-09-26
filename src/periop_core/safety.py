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

from periop_core.models import Conflict, OpenTask, PatientAgendaItem
from periop_core.model_layer import RepairRequirement
from periop_core.enums import (
    AgendaPriority,
    AgendaStatus,
    ConflictStatus,
    Materiality,
    RepairStatus,
    TaskStatus,
)


class ClosureOutcome(str, Enum):
    COMPLETE = "COMPLETE"
    COMPLETE_WITH_OPEN_ACTIONS = "COMPLETE_WITH_OPEN_ACTIONS"
    BLOCKED = "BLOCKED"


@dataclass
class ClosureResult:
    outcome: ClosureOutcome
    blocking_reasons: list[str] = field(default_factory=list)
    open_action_reasons: list[str] = field(default_factory=list)


def evaluate_closure(
    open_tasks: list[OpenTask],
    agenda_items: list[PatientAgendaItem],
    conflicts: list[Conflict],
    repair_requirements: list[RepairRequirement] = (),
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

    if blocking_reasons:
        return ClosureResult(ClosureOutcome.BLOCKED, blocking_reasons, open_action_reasons)
    if open_action_reasons:
        return ClosureResult(
            ClosureOutcome.COMPLETE_WITH_OPEN_ACTIONS, [], open_action_reasons
        )
    return ClosureResult(ClosureOutcome.COMPLETE, [], [])
