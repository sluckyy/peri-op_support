import uuid

from periop_core.enums import (
    AgendaPriority,
    AgendaStatus,
    ConflictStatus,
    ConflictType,
    Materiality,
    TaskPriority,
    TaskStatus,
    TaskType,
)
from periop_core.models import Conflict, OpenTask, PatientAgendaItem
from periop_core.safety import ClosureOutcome, evaluate_closure


def test_critical_unowned_task_blocks_closure():
    session_id = uuid.uuid4()
    task = OpenTask(
        session_id=session_id,
        type=TaskType.SAFETY,
        priority=TaskPriority.CRITICAL,
        reason={"why": "possible difficult airway"},
        owner_ref=None,
    )

    result = evaluate_closure(open_tasks=[task], agenda_items=[], conflicts=[])

    assert result.outcome == ClosureOutcome.BLOCKED
    assert any("INV-010" in r for r in result.blocking_reasons)


def test_critical_task_with_owner_does_not_block():
    session_id = uuid.uuid4()
    task = OpenTask(
        session_id=session_id,
        type=TaskType.SAFETY,
        priority=TaskPriority.CRITICAL,
        reason={"why": "possible difficult airway"},
        owner_ref="anaesthetist-on-call",
        status=TaskStatus.ACKNOWLEDGED,
    )

    result = evaluate_closure(open_tasks=[task], agenda_items=[], conflicts=[])

    assert result.outcome == ClosureOutcome.COMPLETE_WITH_OPEN_ACTIONS


def test_open_conflict_yields_complete_with_open_actions_not_blocked():
    session_id = uuid.uuid4()
    conflict = Conflict(
        session_id=session_id,
        assertion_ids=[uuid.uuid4(), uuid.uuid4()],
        type=ConflictType.VALUE,
        materiality=Materiality.CRITICAL,
        status=ConflictStatus.OPEN,
    )

    result = evaluate_closure(open_tasks=[], agenda_items=[], conflicts=[conflict])

    # A critical conflict must stay visible (INV-004) but a Conflict alone
    # (no unowned critical Task) does not hard-block closure in this model.
    assert result.outcome == ClosureOutcome.COMPLETE_WITH_OPEN_ACTIONS


def test_high_priority_open_agenda_item_yields_open_actions():
    session_id = uuid.uuid4()
    item = PatientAgendaItem(
        session_id=session_id,
        text="worried about waking up during surgery",
        priority=AgendaPriority.HIGH,
        status=AgendaStatus.OPEN,
    )

    result = evaluate_closure(open_tasks=[], agenda_items=[item], conflicts=[])

    assert result.outcome == ClosureOutcome.COMPLETE_WITH_OPEN_ACTIONS
    assert any("INV-014" in r for r in result.open_action_reasons)


def test_nothing_open_yields_complete():
    result = evaluate_closure(open_tasks=[], agenda_items=[], conflicts=[])
    assert result.outcome == ClosureOutcome.COMPLETE
    assert result.blocking_reasons == []
    assert result.open_action_reasons == []
