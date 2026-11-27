"""Clinician-reviewed question skip map: which conditional follow-up
questions stop applying once their parent screening question is answered
"no" (docs/clinical/question_skip_map.csv).

Why a hand-built map: the Clinical Dataset's `Trigger` column is prose
(121 distinct wordings, 23 rows just "Positive or relevant upstream
response"), so conditional activation can't be parsed mechanically
without inventing clinical judgement. Each rule here is that judgement
made explicit, with a rationale, and only rules whose status is APPROVED
(clinician sign-off) have any effect -- PROPOSED rules are inert.

Structural guarantees enforced at load time (fail loud, not silently
skip): every concept exists; no M0/M1 requirement is ever skippable
(universal or mandatory screens are always asked); and no rule's child is
another rule's parent, so a skipped question can never cascade.
"""
from __future__ import annotations

import csv
import pathlib
from dataclasses import dataclass
from functools import lru_cache

from periop_core.dataset import REPO_ROOT, default_requirements
from periop_core.enums import RequirementClass
from periop_core.models import Requirement

DEFAULT_SKIP_MAP_CSV = REPO_ROOT / "docs" / "clinical" / "question_skip_map.csv"
_NEVER_SKIPPABLE = {RequirementClass.M0, RequirementClass.M1}
_STATUSES = {"PROPOSED", "APPROVED", "REJECTED"}


@dataclass(frozen=True)
class SkipRule:
    rule_id: str
    parents: tuple[str, ...]
    children: tuple[str, ...]
    rationale: str
    status: str
    approved_by: str = ""

    @property
    def approved(self) -> bool:
        return self.status == "APPROVED"


def validate_rules(rules: list[SkipRule], requirements: dict[str, Requirement]) -> None:
    all_parents = {p for r in rules for p in r.parents}
    seen_ids: set[str] = set()
    for rule in rules:
        if rule.rule_id in seen_ids:
            raise ValueError(f"{rule.rule_id}: duplicate rule_id")
        seen_ids.add(rule.rule_id)
        if rule.status not in _STATUSES:
            raise ValueError(f"{rule.rule_id}: unknown status {rule.status!r}")
        if rule.approved and not rule.approved_by:
            raise ValueError(f"{rule.rule_id}: APPROVED rules must name who approved them")
        if not rule.parents or not rule.children:
            raise ValueError(f"{rule.rule_id}: needs at least one parent and one child")
        for concept in rule.parents + rule.children:
            if concept not in requirements:
                raise ValueError(f"{rule.rule_id}: unknown concept {concept!r}")
        for child in rule.children:
            if requirements[child].requiredness in _NEVER_SKIPPABLE:
                raise ValueError(
                    f"{rule.rule_id}: {child} is {requirements[child].requiredness.value} "
                    "and must always be asked"
                )
            if child in all_parents:
                raise ValueError(f"{rule.rule_id}: {child} is also a parent in another rule (no chains)")


def load_skip_rules(
    csv_path: pathlib.Path = DEFAULT_SKIP_MAP_CSV,
    requirements: dict[str, Requirement] | None = None,
) -> list[SkipRule]:
    with csv_path.open(newline="", encoding="utf-8") as f:
        rules = [
            SkipRule(
                rule_id=row["rule_id"].strip(),
                parents=tuple(row["skip_when_all_negated"].split()),
                children=tuple(row["children"].split()),
                rationale=row["rationale"].strip(),
                status=row["status"].strip().upper(),
                approved_by=row.get("approved_by", "").strip(),
            )
            for row in csv.DictReader(f)
            if row["rule_id"].strip()
        ]
    validate_rules(rules, requirements if requirements is not None else default_requirements())
    return rules


@lru_cache(maxsize=1)
def approved_skip_rules() -> tuple[SkipRule, ...]:
    return tuple(r for r in load_skip_rules() if r.approved)


def skipped_children(
    rules: tuple[SkipRule, ...] | list[SkipRule], negated: set[str]
) -> dict[str, set[str]]:
    """{child concept: parent concepts that made it not applicable} for
    every rule whose parents are ALL negated."""
    out: dict[str, set[str]] = {}
    for rule in rules:
        if all(p in negated for p in rule.parents):
            for child in rule.children:
                out.setdefault(child, set()).update(rule.parents)
    return out


def choose_next_target(
    candidates: list[str], answered: set[str], rules: tuple[SkipRule, ...] | list[SkipRule]
) -> str | None:
    """First candidate (already in priority order) that isn't waiting on an
    unanswered parent -- so e.g. last menstrual period (C1) waits for the
    pregnancy question (C4) even though gap priority would ask it first.
    Falls back to plain priority order if everything left is waiting."""
    waits_on: dict[str, set[str]] = {}
    for rule in rules:
        for child in rule.children:
            waits_on.setdefault(child, set()).update(rule.parents)
    for concept in candidates:
        if not (waits_on.get(concept, set()) - answered):
            return concept
    return candidates[0] if candidates else None
