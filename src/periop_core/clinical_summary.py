"""Clinician-facing structured pre-op summary, built deterministically
from governed state (working facts, conflicts, conflict reviews,
requirement states, tasks, repairs, closure preview). This is the spec's
"deterministic structured view": the primary clinician summary and the
fallback for any LLM-drafted narrative (LLM-005 is draft-only).

Guardrails it encodes:
- SB-019: it never claims clinician review. `review_status` is always
  NOT_CLINICIAN_REVIEWED -- there is no verification workflow yet.
- "No hidden critical issue": anything that blocks closure, every open
  conflict (both sides verbatim), an unsure answer on a safety-critical
  concept, and open repairs/tasks go in `attention`, ahead of findings.
- Every finding carries its sources (who said what, when, and how it was
  entered) for drill-down; nothing is paraphrased away.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from periop_core.enums import (
    AssertionState,
    ConflictStatus,
    ContradictionStatus,
    InformationState,
    Materiality,
    RepairStatus,
    RequirementClass,
    TaskStatus,
    VerificationState,
)
from periop_core.models import (
    Assertion,
    Conflict,
    ConflictReview,
    OpenTask,
    Requirement,
    RequirementState,
    Session,
    WorkingFact,
)
from periop_core.reconciliation import CRITICAL_CONCEPT_PREFIXES

REVIEW_STATUS = "NOT_CLINICIAN_REVIEWED"

_ANSWER_TEXT = {
    AssertionState.AFFIRMED: "Yes",
    AssertionState.NEGATED: "No",
    AssertionState.UNCERTAIN: "Unsure",
    AssertionState.UNKNOWN: "Doesn't know",
    AssertionState.DECLINED: "Declined to answer",
    AssertionState.CONDITIONAL: "Sometimes / under some conditions",
}
_UNSURE_STATES = {AssertionState.UNCERTAIN, AssertionState.UNKNOWN, AssertionState.DECLINED}
_POSITIVE_STATES = {AssertionState.AFFIRMED, AssertionState.CONDITIONAL}
_VERIFICATION_TEXT = {
    VerificationState.CONFIRMED: "confirmed",
    VerificationState.UNCONFIRMED: "patient-reported, unverified",
    VerificationState.STALE: "stale — needs re-confirming",
    VerificationState.CONFLICTED: "conflicting sources",
    VerificationState.UNKNOWN: "unknown",
}
_SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MODERATE": 2, "LOW": 3}


class FindingSource(BaseModel):
    assertion_id: uuid.UUID
    source_type: str
    speaker: str
    said: str
    value: Any | None = None
    answer: str
    recorded_at: datetime
    entered_via: str | None = None


class Finding(BaseModel):
    concept_id: str
    concept: str
    domain: str
    answer: str
    detail: str | None = None
    verification: str
    safety_critical: bool
    sources: list[FindingSource]


class AttentionItem(BaseModel):
    kind: str  # closure_block | conflict | unsure_safety_answer | repair | task
    severity: str  # CRITICAL | HIGH | MODERATE | LOW
    title: str
    detail: str
    concept_id: str | None = None
    concept: str | None = None
    sources: list[FindingSource] = []


class DomainSection(BaseModel):
    domain: str
    positives: list[Finding] = []
    unsure: list[Finding] = []
    negatives: list[Finding] = []
    conflicting: list[Finding] = []


class UnansweredItem(BaseModel):
    concept_id: str
    concept: str
    domain: str
    requirement_class: str


class NotApplicableItem(BaseModel):
    concept_id: str
    concept: str
    domain: str
    because: list[str]


class SummaryCounts(BaseModel):
    answered: int
    positives: int
    negatives: int
    unsure: int
    conflicting: int
    unanswered: int
    unanswered_mandatory: int
    not_applicable: int


class ClinicalSummary(BaseModel):
    session_id: uuid.UUID
    subject_ref: str
    session_status: str
    generated_at: datetime
    review_status: str = REVIEW_STATUS
    closure_outcome: str
    attention: list[AttentionItem]
    safety_findings: list[Finding]
    domains: list[DomainSection]
    unanswered_mandatory: list[UnansweredItem]
    not_applicable: list[NotApplicableItem]
    counts: SummaryCounts


def _is_safety_critical(concept_id: str) -> bool:
    return any(concept_id.startswith(p) for p in CRITICAL_CONCEPT_PREFIXES)


def _source(a: Assertion) -> FindingSource:
    return FindingSource(
        assertion_id=a.assertion_id,
        source_type=a.source.source_type,
        speaker=a.source.speaker.value,
        said=a.concept.original_text,
        value=a.value,
        answer=_ANSWER_TEXT[a.assertion_state],
        recorded_at=a.assertion_time,
        entered_via=(a.provenance or {}).get("entered_via"),
    )


def _value_text(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return value if isinstance(value, str) else str(value)


def build_clinical_summary(
    *,
    session: Session,
    facts: list[WorkingFact],
    conflicts: list[Conflict],
    conflict_reviews: list[ConflictReview],
    requirement_states: list[RequirementState],
    tasks: list[OpenTask],
    repairs: list,
    closure_outcome: str,
    blocking_reasons: list[str],
    assertions: list[Assertion],
    requirements: dict[str, Requirement],
    labels: dict[str, dict[str, str]],
    now: datetime | None = None,
) -> ClinicalSummary:
    by_id = {a.assertion_id: a for a in assertions}

    def label(concept_id: str) -> tuple[str, str]:
        meta = labels.get(concept_id, {})
        return meta.get("concept", concept_id), meta.get("domain", "Other")

    attention: list[AttentionItem] = [
        AttentionItem(kind="closure_block", severity="CRITICAL", title="Closure is blocked", detail=reason)
        for reason in blocking_reasons
    ]

    # Conflict rows are recomputed (new ids) on every pass; a review is
    # keyed by its disagreeing assertion set, which is stable.
    reviews_by_assertions = {frozenset(s.assertion_id for s in r.sides): r for r in conflict_reviews}
    for conflict in conflicts:
        if conflict.status is not ConflictStatus.OPEN:
            continue
        sides = [by_id[a] for a in conflict.assertion_ids if a in by_id]
        if not sides:
            continue
        concept_id = sides[0].concept.code or sides[0].concept.original_text
        concept, _ = label(concept_id)
        review = reviews_by_assertions.get(frozenset(a.assertion_id for a in sides))
        resolution = review.resolution if review is not None else None
        if review is None or review.status is ContradictionStatus.OPEN or resolution is None:
            review_text = "Awaiting clinician review."
        elif review.status is ContradictionStatus.ESCALATED:
            review_text = f"Escalated by {resolution.resolved_by}: {resolution.rationale}"
        else:
            review_text = (f"Reconciled by {resolution.resolved_by} "
                           f"(chose {resolution.resolved_value!r}): {resolution.rationale}")
        attention.append(AttentionItem(
            kind="conflict",
            severity=conflict.materiality.value,
            title=f"Conflicting answers: {concept}",
            detail=f"{conflict.type.value.lower()} conflict between {len(sides)} sources. {review_text}",
            concept_id=concept_id,
            concept=concept,
            sources=[_source(a) for a in sides],
        ))

    for repair in repairs:
        if repair.status is RepairStatus.OPEN and repair.materiality in (Materiality.CRITICAL, Materiality.HIGH):
            attention.append(AttentionItem(kind="repair", severity=repair.materiality.value,
                                           title="Open conversational repair", detail=repair.description))
    for task in tasks:
        if task.status in (TaskStatus.OPEN, TaskStatus.ACKNOWLEDGED):
            severity = "CRITICAL" if task.priority.value == "CRITICAL" else "HIGH"
            owner = task.owner_ref or "UNOWNED"
            attention.append(AttentionItem(kind="task", severity=severity,
                                           title=f"Open {task.type.value.lower()} task ({owner})",
                                           detail=str(task.reason.get("why") or task.reason)))

    domain_order = list(dict.fromkeys(meta.get("domain", "Other") for meta in labels.values()))
    sections: dict[str, DomainSection] = {}
    safety_findings: list[Finding] = []
    counts = dict(positives=0, negatives=0, unsure=0, conflicting=0)

    for fact in facts:
        concept_id = fact.concept.code
        if not concept_id or concept_id not in requirements:
            continue
        concept, domain = label(concept_id)
        supporting = [by_id[a] for a in fact.supporting_assertion_ids if a in by_id]
        if not supporting:
            continue
        section = sections.setdefault(domain, DomainSection(domain=domain))
        critical = _is_safety_critical(concept_id)
        if fact.verification_state is VerificationState.CONFLICTED:
            finding = Finding(concept_id=concept_id, concept=concept, domain=domain,
                              answer="Conflicting sources — see Needs attention",
                              verification=_VERIFICATION_TEXT[fact.verification_state],
                              safety_critical=critical, sources=[_source(a) for a in supporting])
            section.conflicting.append(finding)
            counts["conflicting"] += 1
            continue

        state = supporting[0].assertion_state  # an agreeing fact shares one state
        value = _value_text(fact.value)
        answer = value if (value and state is AssertionState.AFFIRMED) else _ANSWER_TEXT[state]
        finding = Finding(
            concept_id=concept_id, concept=concept, domain=domain, answer=answer,
            detail=value if value and value != answer else None,
            verification=_VERIFICATION_TEXT[fact.verification_state],
            safety_critical=critical, sources=[_source(a) for a in supporting],
        )
        if state in _POSITIVE_STATES:
            section.positives.append(finding)
            counts["positives"] += 1
            if critical:
                safety_findings.append(finding)
        elif state is AssertionState.NEGATED:
            section.negatives.append(finding)
            counts["negatives"] += 1
        else:
            section.unsure.append(finding)
            counts["unsure"] += 1
            if critical and state in _UNSURE_STATES:
                attention.append(AttentionItem(
                    kind="unsure_safety_answer", severity="HIGH",
                    title=f"Unresolved safety-critical answer: {concept}",
                    detail=f"Patient answered '{_ANSWER_TEXT[state]}'. Needs clarification or another source.",
                    concept_id=concept_id, concept=concept, sources=finding.sources,
                ))

    unanswered_mandatory: list[UnansweredItem] = []
    not_applicable: list[NotApplicableItem] = []
    unanswered = 0
    for state in requirement_states:
        concept, domain = label(state.requirement_id)
        requirement = requirements.get(state.requirement_id)
        if state.information_state is InformationState.NOT_ASKED:
            unanswered += 1
            if requirement and requirement.requiredness in (RequirementClass.M0, RequirementClass.M1):
                unanswered_mandatory.append(UnansweredItem(
                    concept_id=state.requirement_id, concept=concept, domain=domain,
                    requirement_class=requirement.requiredness.value,
                ))
        elif state.information_state is InformationState.NOT_APPLICABLE:
            parents = sorted({label(by_id[a].concept.code or "")[0] for a in state.evidence_refs if a in by_id})
            not_applicable.append(NotApplicableItem(
                concept_id=state.requirement_id, concept=concept, domain=domain,
                because=[f"{p}: No" for p in parents],
            ))

    attention.sort(key=lambda item: _SEVERITY_ORDER.get(item.severity, 9))
    ordered_sections = [sections[d] for d in domain_order if d in sections] + [
        s for d, s in sections.items() if d not in domain_order
    ]
    answered = sum(counts.values())
    return ClinicalSummary(
        session_id=session.session_id,
        subject_ref=session.subject_ref,
        session_status=session.status.value,
        generated_at=now or datetime.now(timezone.utc),
        closure_outcome=closure_outcome,
        attention=attention,
        safety_findings=safety_findings,
        domains=ordered_sections,
        unanswered_mandatory=unanswered_mandatory,
        not_applicable=not_applicable,
        counts=SummaryCounts(
            answered=answered, unanswered=unanswered, unanswered_mandatory=len(unanswered_mandatory),
            not_applicable=len(not_applicable), **counts,
        ),
    )
