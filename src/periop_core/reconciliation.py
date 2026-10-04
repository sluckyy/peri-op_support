"""A minimal, real (not stubbed) implementation of the happy-path and
basic-conflict cases of the 12-step Reconciliation Algorithm
(docs/exports/reconciliation_algorithm.csv).

Scope honestly stated: this implements steps 1-2 (normalise/partition by
grouping on concept identity + assertion_state), step 3 (freshness --
see `_assess_freshness` below for exactly how, and its documented
limitation), step 5 (relationship detection: SAME vs CONFLICTING), step 6
(materiality classification, keyword-based approximation) and step 11
(construct current WorkingFact, never erasing dissent). Step 4 proper
(fitness-based tie-breaking using the Source Authority Matrix) and steps
7-10 (deterministic auto-resolution, conversational clarification,
collateral retrieval, human verification) and 12 (FHIR projection) are
NOT implemented here -- they require either a concept-to-Source-Authority-
Matrix-datatype mapping that doesn't exist yet (see source_authority.py's
module docstring), or the gap engine / workflow / FHIR adapter layers, and
are left as TODOs for a later phase. See docs/addenda and Full Spec §4,
Table 24 Phase 1 for what Phase 1 actually requires.

Known simplification (documented, not hidden): assertions are grouped by
`concept.code` if present, else the lower-cased stripped `original_text`.
A full implementation would use the Concept Mapping register to resolve
synonyms/hierarchy via the terminology service (TERM-008); that is not
built here.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

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
# auto-resolved"). Public (not `_`-prefixed) because periop_core.safety
# also needs it, to decide whether an unresolved ConflictReview on one of
# these concepts should block closure the same way a CRITICAL Conflict's
# materiality does.
CRITICAL_CONCEPT_PREFIXES = ("CTX-001", "CTX-003", "CTX-004", "CTX-005", "ALL-", "ANAES-", "MED-")

# Step 3 (assess freshness), scope honestly stated: the Reconciliation
# Algorithm calls for a *datatype-specific* freshness rule (Source
# Authority Matrix's "Freshness consideration" column -- e.g. "very high"
# for current medication/symptoms vs "longitudinal"/persistent for
# allergy or family history), which needs the same concept-to-matrix-
# datatype mapping that step 4 (source fitness) needs and that doesn't
# exist yet (see source_authority.py). Rather than either skip freshness
# entirely or apply one threshold to everything (which would misclassify
# durably-valid facts like a confirmed allergy as stale), this uses a
# single conservative default threshold *except* for the domains the
# matrix itself describes as persistent/longitudinal, which are exempted
# from staleness altogether. Only applies to *agreeing* assertion groups
# (a single current value) -- a disagreement between an old and a new
# assertion is a conflict-resolution question (step 7, auto-resolution),
# not this function's job, and remains unresolved exactly as before (see
# REC-T005 in test_reconciliation.py).
_EVERGREEN_PREFIXES = ("ALL-", "FAM-", "CTX-001")  # allergy, family history, identity
_STALE_AFTER = timedelta(days=180)


def _concept_key(assertion: Assertion) -> str:
    if assertion.concept.code:
        return assertion.concept.code
    return assertion.concept.original_text.strip().lower()


def _classify_materiality(concept_key: str) -> Materiality:
    if any(concept_key.startswith(p) for p in CRITICAL_CONCEPT_PREFIXES):
        return Materiality.CRITICAL
    return Materiality.MODERATE


def _as_naive_utc(dt: datetime) -> datetime:
    """`Assertion.assertion_time` defaults to the naive `datetime.utcnow()`
    everywhere internally, but a client-supplied ISO timestamp (the demo
    API's optional backdating field) can arrive timezone-aware -- normalise
    both to naive UTC before comparing, rather than risk a TypeError."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _assess_freshness(
    concept_key: str, group: list[Assertion], now: datetime
) -> tuple[VerificationState, dict]:
    """Returns the verification_state an *agreeing* group should carry
    (UNCONFIRMED unless stale) plus a freshness record for
    WorkingFact.freshness explaining the call. Uses `assertion_time` (when
    the assertion was captured) as a proxy for how current the underlying
    fact is -- `Assertion.event_time` (the actual clinical event date)
    would be more faithful to the spec's intent but has no defined
    internal parser yet (see Assertion.event_time's docstring); that's a
    documented gap, not an oversight.
    """
    now = _as_naive_utc(now)
    most_recent = max(_as_naive_utc(a.assertion_time) for a in group)
    if any(concept_key.startswith(p) for p in _EVERGREEN_PREFIXES):
        return VerificationState.UNCONFIRMED, {
            "most_recent_assertion_time": most_recent.isoformat(),
            "classification": "EXEMPT",
            "note": "Evergreen domain (allergy/family history/identity) -- not subject to staleness.",
        }
    age = now - most_recent
    if age > _STALE_AFTER:
        return VerificationState.STALE, {
            "most_recent_assertion_time": most_recent.isoformat(),
            "classification": "STALE",
            "threshold_days": _STALE_AFTER.days,
            "note": "Older than the generic default threshold -- not yet a per-datatype rule.",
        }
    return VerificationState.UNCONFIRMED, {
        "most_recent_assertion_time": most_recent.isoformat(),
        "classification": "CURRENT",
        "threshold_days": _STALE_AFTER.days,
    }


def _values_agree(a: Assertion, b: Assertion) -> bool:
    if a.assertion_state != b.assertion_state:
        return False
    if a.value is None and b.value is None:
        return True
    return a.value == b.value


def reconcile(
    assertions: list[Assertion],
    source_authority_matrix: dict[str, SourceAuthorityRule] | None = None,
    now: datetime | None = None,
) -> tuple[list[WorkingFact], list[Conflict]]:
    """Group assertions by concept identity and produce WorkingFacts and
    Conflicts. Never drops an assertion (INV-002/INV-004 spirit): every
    assertion ends up referenced by exactly one WorkingFact's supporting
    or dissenting list.

    A disagreeing group always becomes an OPEN Conflict plus a CONFLICTED
    WorkingFact -- materiality classification (step 6) only decides the
    Conflict's `materiality`, not whether it's auto-resolved; nothing here
    auto-resolves a disagreement (step 7 is not implemented -- see the
    module docstring and REC-T005 in test_reconciliation.py).

    `source_authority_matrix` is accepted for forward compatibility (a
    caller may pass `default_source_authority_matrix()`), but this minimal
    implementation does not yet use per-datatype fitness rules — see the
    module docstring for exactly what step 4 would still need.

    `now` (defaults to `datetime.utcnow()`) is the reference point for
    step 3's freshness assessment -- see `_assess_freshness`.
    """
    del source_authority_matrix  # accepted, not yet used -- see docstring
    if now is None:
        now = datetime.utcnow()

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
            verification_state, freshness = _assess_freshness(concept_key, group, now)
            working_facts.append(
                WorkingFact(
                    session_id=session_id,
                    concept=concept,
                    value=group[0].value,
                    verification_state=verification_state,
                    freshness=freshness,
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
