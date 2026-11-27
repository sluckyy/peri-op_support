"""Clinician-reviewed red-flag escalation map
(docs/clinical/escalation_map.csv), implementing the spec's escalation
framework (§8.2) for the Clinical Dataset's Red_flag_rule column.

Each rule says which answers (assertion states) on which concepts raise
an escalation, its ESC class, and its tier:
- URGENT (ESC-001): an OpenTask at CRITICAL priority -- which blocks
  closure until someone owns it (INV-010) -- plus a fixed, approved
  safety message shown to the patient immediately. §8.3: approved
  instructions may be communicated but never modified, so the message is
  data in this file, never model-generated.
- RED: prompt clinician review -> URGENT-priority task.
- AMBER: review/optimisation -> ROUTINE-priority task.

Only APPROVED rules (named approver) take effect. Escalation is
deliberately conservative: any assertion on the concept in a trigger
state raises it, including one side of a conflict, and a later "no"
never silently withdraws it -- a clinician resolves the task.

Scope honestly stated: rules that depend on a value (e.g. "recent"
seizure date, missed dialysis, limiting-symptom category) can't be
evaluated from a yes/no answer and are not in the map; those values are
still visible in the clinician summary.
"""
from __future__ import annotations

import csv
import pathlib
import uuid
from dataclasses import dataclass
from functools import lru_cache

from periop_core.dataset import REPO_ROOT, default_concept_labels, default_requirements
from periop_core.enums import AssertionState, TaskPriority, TaskStatus, TaskType
from periop_core.models import Assertion, OpenTask, Requirement

DEFAULT_ESCALATION_MAP_CSV = REPO_ROOT / "docs" / "clinical" / "escalation_map.csv"
TIERS = ("URGENT", "RED", "AMBER")
_CLASSES = {f"ESC-{i:03d}" for i in range(1, 13)}
_STATUSES = {"PROPOSED", "APPROVED", "REJECTED"}
_TASK_NAMESPACE = uuid.UUID("2f0c9f3e-7d1b-4c8e-a6b5-5f1e9d3c7a21")
_SAFETY_CLASSES = {"ESC-001", "ESC-002", "ESC-003", "ESC-004", "ESC-005"}


@dataclass(frozen=True)
class EscalationRule:
    rule_id: str
    concepts: tuple[str, ...]
    trigger_states: frozenset[AssertionState]
    escalation_class: str
    tier: str
    patient_message: str
    rationale: str
    status: str
    approved_by: str = ""

    @property
    def approved(self) -> bool:
        return self.status == "APPROVED"


@dataclass(frozen=True)
class Escalation:
    rule: EscalationRule
    concept_id: str
    assertion_ids: tuple[uuid.UUID, ...]


def validate_rules(rules: list[EscalationRule], requirements: dict[str, Requirement]) -> None:
    seen_ids: set[str] = set()
    owner: dict[tuple[str, AssertionState], str] = {}
    for rule in rules:
        if rule.rule_id in seen_ids:
            raise ValueError(f"{rule.rule_id}: duplicate rule_id")
        seen_ids.add(rule.rule_id)
        if rule.status not in _STATUSES:
            raise ValueError(f"{rule.rule_id}: unknown status {rule.status!r}")
        if rule.approved and not rule.approved_by:
            raise ValueError(f"{rule.rule_id}: APPROVED rules must name who approved them")
        if rule.tier not in TIERS:
            raise ValueError(f"{rule.rule_id}: unknown tier {rule.tier!r}")
        if rule.escalation_class and rule.escalation_class not in _CLASSES:
            raise ValueError(f"{rule.rule_id}: unknown escalation class {rule.escalation_class!r}")
        if rule.tier == "URGENT" and not rule.patient_message:
            raise ValueError(f"{rule.rule_id}: URGENT rules need an approved patient safety message")
        if rule.tier != "URGENT" and rule.patient_message:
            raise ValueError(f"{rule.rule_id}: only URGENT rules may message the patient")
        if not rule.concepts or not rule.trigger_states:
            raise ValueError(f"{rule.rule_id}: needs concepts and trigger states")
        for concept in rule.concepts:
            if concept not in requirements:
                raise ValueError(f"{rule.rule_id}: unknown concept {concept!r}")
            for state in rule.trigger_states:
                key = (concept, state)
                if key in owner:
                    raise ValueError(
                        f"{rule.rule_id}: {concept} {state.value} is already covered by {owner[key]}"
                    )
                owner[key] = rule.rule_id


def load_escalation_rules(
    csv_path: pathlib.Path = DEFAULT_ESCALATION_MAP_CSV,
    requirements: dict[str, Requirement] | None = None,
) -> list[EscalationRule]:
    rules = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if not row["rule_id"].strip():
                continue
            try:
                states = frozenset(AssertionState(s) for s in row["trigger_states"].split())
            except ValueError as exc:
                raise ValueError(f"{row['rule_id']}: {exc}") from None
            rules.append(EscalationRule(
                rule_id=row["rule_id"].strip(),
                concepts=tuple(row["concepts"].split()),
                trigger_states=states,
                escalation_class=row["escalation_class"].strip(),
                tier=row["tier"].strip().upper(),
                patient_message=row["patient_message"].strip(),
                rationale=row["rationale"].strip(),
                status=row["status"].strip().upper(),
                approved_by=row.get("approved_by", "").strip(),
            ))
    validate_rules(rules, requirements if requirements is not None else default_requirements())
    return rules


@lru_cache(maxsize=1)
def approved_escalation_rules() -> tuple[EscalationRule, ...]:
    return tuple(r for r in load_escalation_rules() if r.approved)


def evaluate(rules, assertions: list[Assertion]) -> list[Escalation]:
    """Every (rule, concept) with at least one assertion in a trigger state."""
    by_concept: dict[str, list[Assertion]] = {}
    for a in assertions:
        if a.concept.code:
            by_concept.setdefault(a.concept.code, []).append(a)
    out = []
    for rule in rules:
        for concept in rule.concepts:
            hits = [a for a in by_concept.get(concept, []) if a.assertion_state in rule.trigger_states]
            if hits:
                out.append(Escalation(rule, concept, tuple(a.assertion_id for a in hits)))
    return out


def task_id_for(session_id: uuid.UUID, rule_id: str, concept_id: str) -> uuid.UUID:
    """Deterministic, so re-evaluating never raises the same escalation twice."""
    return uuid.uuid5(_TASK_NAMESPACE, f"{session_id}:{rule_id}:{concept_id}")


def task_for(session_id: uuid.UUID, esc: Escalation) -> OpenTask:
    rule = esc.rule
    if rule.tier == "URGENT":
        task_type, priority = TaskType.SAFETY, TaskPriority.CRITICAL
    elif rule.tier == "RED":
        task_type = TaskType.SAFETY if rule.escalation_class in _SAFETY_CLASSES else TaskType.CLINICAL_REVIEW
        priority = TaskPriority.URGENT
    else:
        task_type, priority = TaskType.CLINICAL_REVIEW, TaskPriority.ROUTINE
    concept = default_concept_labels().get(esc.concept_id, {}).get("concept", esc.concept_id)
    return OpenTask(
        task_id=task_id_for(session_id, rule.rule_id, esc.concept_id),
        session_id=session_id,
        type=task_type,
        priority=priority,
        status=TaskStatus.OPEN,
        reason={
            "why": rule.rationale,
            "rule_id": rule.rule_id,
            "tier": rule.tier,
            "escalation_class": rule.escalation_class or None,
            "concept_id": esc.concept_id,
            "concept": concept,
            "trigger_assertion_ids": [str(a) for a in esc.assertion_ids],
            "patient_message": rule.patient_message or None,
            "approved_by": rule.approved_by,
        },
    )
