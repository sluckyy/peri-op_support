"""A minimal, real (not stubbed) implementation of the happy-path and
basic-conflict cases of the 12-step Reconciliation Algorithm
(docs/exports/reconciliation_algorithm.csv).

Scope honestly stated: this implements steps 1-2 (normalise/partition by
grouping on concept identity + assertion_state), step 4 (source fitness via
the Source Authority Matrix), step 5 (relationship detection: SAME vs
CONFLICTING), step 6 (materiality classification, keyword-based
approximation) and step 11 (construct current WorkingFact, never erasing
dissent). Steps 3 (freshness), 7-10 (deterministic auto-resolution,
conversational clarification, collateral retrieval, human verification)
and 12 (FHIR projection) are NOT implemented here — they require the
gap engine / workflow / FHIR adapter layers respectively and are left as
TODOs for a later phase. See docs/addenda and Full Spec §4, Table 24
Phase 1 for what Phase 1 actually requires.

Known simplification (documented, not hidden): assertions are grouped by
`concept.code` if present, else the lower-cased stripped `original_text`.
A full implementation would use the Concept Mapping register to resolve
synonyms/hierarchy via the terminology service (TERM-008); that is not
built here.
"""
from __future__ import annotations

import uuid
from collections import defaultdict

from periop_core.enums import (
    AssertionState,
    ConflictStatus,
    ConflictType,
    Materiality,
    VerificationState,
)
from periop_core.models import Assertion, Conflict, WorkingFact
from periop_core.source_authority import SourceAuthorityRule

# Concept-code prefixes treated as CRITICAL materiality on conflict,
# regardless of matrix text-matching (identity/procedure/allergy/airway/
# anticoagulant-adjacent domains -- see Conflict Taxonomy CF-001..CF-009
# and §4.3: "high/critical conflicts involving identity, procedure,
# airway, severe allergy, anticoagulants ... cannot be silently
# auto-resolved").
_CRITICAL_PREFIXES = ("CTX-001", "CTX-003", "CTX-004", "CTX-005", "ALL-", "ANAES-", "MED-")


def _concept_key(assertion: Assertion) -> str:
    if assertion.concept.code:
        return assertion.concept.code
    return assertion.concept.original_text.strip().lower()


def _classify_materiality(concept_key: str) -> Materiality:
    if any(concept_key.startswith(p) for p in _CRITICAL_PREFIXES):
        return Materiality.CRITICAL
    return Materiality.MODERATE


def _values_agree(a: Assertion, b: Assertion) -> bool:
    if a.assertion_state != b.assertion_state:
        return False
    if a.value is None and b.value is None:
        return True
    return a.value == b.value


def reconcile(
    assertions: list[Assertion],
    source_authority_matrix: dict[str, SourceAuthorityRule] | None = None,
) -> tuple[list[WorkingFact], list[Conflict]]:
    """Group assertions by concept identity and produce WorkingFacts and
    Conflicts. Never drops an assertion (INV-002/INV-004 spirit): every
    assertion ends up referenced by exactly one WorkingFact's supporting
    or dissenting list.

    `source_authority_matrix` is accepted for forward compatibility (a
    caller may pass `default_source_authority_matrix()`), but this minimal
    implementation does not yet use per-datatype fitness rules to break
    ties — it only uses materiality classification (step 6) to decide
    whether a WorkingFact for a disagreeing group may be marked CONFIRMED
    or must be marked CONFLICTED. A real fitness-based tie-break (step 4
    proper) is a documented gap, not silently assumed away.
    """
    del source_authority_matrix  # accepted, not yet used -- see docstring

    groups: dict[str, list[Assertion]] = defaultdict(list)
    for a in assertions:
        groups[_concept_key(a)].append(a)

    working_facts: list[WorkingFact] = []
    conflicts: list[Conflict] = []

    for concept_key, group in groups.items():
        session_id = group[0].session_id
        concept = group[0].concept

        # Step 5: detect relationship. All pairwise agree -> SAME.
        all_agree = all(
            _values_agree(group[0], other) for other in group[1:]
        )

        if all_agree:
            working_facts.append(
                WorkingFact(
                    session_id=session_id,
                    concept=concept,
                    value=group[0].value,
                    verification_state=VerificationState.UNCONFIRMED,
                    supporting_assertion_ids=[a.assertion_id for a in group],
                    dissenting_assertion_ids=[],
                )
            )
            continue

        # Disagreement: never silently pick a winner (§4.2, INV-002/004).
        materiality = _classify_materiality(concept_key)
        conflicts.append(
            Conflict(
                session_id=session_id,
                assertion_ids=[a.assertion_id for a in group],
                type=(
                    ConflictType.NEGATION
                    if {a.assertion_state for a in group}
                    >= {AssertionState.AFFIRMED, AssertionState.NEGATED}
                    else ConflictType.VALUE
                ),
                materiality=materiality,
                status=ConflictStatus.OPEN,
            )
        )
        working_facts.append(
            WorkingFact(
                session_id=session_id,
                concept=concept,
                value=None,
                verification_state=VerificationState.CONFLICTED,
                # All retained as "supporting" in the sense of none being
                # erased; the Conflict object is the record of dissent.
                supporting_assertion_ids=[a.assertion_id for a in group],
                dissenting_assertion_ids=[],
            )
        )

    return working_facts, conflicts
