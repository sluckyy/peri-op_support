import uuid

import pytest
from pydantic import ValidationError

from periop_core.enums import (
    AssertionState,
    Certainty,
    ConflictType,
    ContradictionStatus,
    Materiality,
    Speaker,
)
from periop_core.models import (
    Assertion,
    ConceptReference,
    Conflict,
    ConflictReview,
    ConflictReviewSide,
    SourceReference,
    WorkingFact,
)


def _assertion(**overrides):
    defaults = dict(
        session_id=uuid.uuid4(),
        subject_ref="pt-1",
        concept=ConceptReference(original_text="chest pain"),
        assertion_state=AssertionState.AFFIRMED,
        source=SourceReference(source_type="PATIENT", speaker=Speaker.PATIENT),
        certainty=Certainty.EXPLICIT,
        provenance={"extractor_version": "test-1"},
    )
    defaults.update(overrides)
    return Assertion(**defaults)


def test_assertion_requires_non_empty_provenance():
    # INV-001
    with pytest.raises(ValidationError, match="INV-001"):
        _assertion(provenance={})


def test_assertion_cannot_supersede_itself():
    a = _assertion()
    with pytest.raises(ValidationError, match="cannot supersede itself"):
        Assertion(
            **{
                **a.model_dump(exclude={"supersedes_assertion_id"}),
                "supersedes_assertion_id": a.assertion_id,
            }
        )


def test_working_fact_requires_at_least_one_supporting_assertion():
    # INV-003
    with pytest.raises(ValidationError, match="INV-003"):
        WorkingFact(
            session_id=uuid.uuid4(),
            concept=ConceptReference(original_text="chest pain"),
            verification_state="UNCONFIRMED",
            supporting_assertion_ids=[],
        )


def test_conflict_requires_at_least_two_assertions():
    with pytest.raises(ValidationError, match="at least two"):
        Conflict(
            session_id=uuid.uuid4(),
            assertion_ids=[uuid.uuid4()],
            type=ConflictType.VALUE,
            materiality=Materiality.LOW,
        )


def test_only_low_moderate_conflicts_report_as_auto_resolvable():
    session_id = uuid.uuid4()
    ids = [uuid.uuid4(), uuid.uuid4()]
    for m, expected in (
        (Materiality.LOW, True),
        (Materiality.MODERATE, True),
        (Materiality.HIGH, False),
        (Materiality.CRITICAL, False),
    ):
        conflict = Conflict(
            session_id=session_id, assertion_ids=ids, type=ConflictType.VALUE, materiality=m
        )
        assert conflict.can_auto_resolve() is expected


def _conflict_review_sides():
    return [
        ConflictReviewSide(
            assertion_id=uuid.uuid4(),
            source_type="PATIENT",
            speaker=Speaker.PATIENT,
            value="no reaction",
            original_text="patient says no reaction at all",
            recorded_at="2024-10-02T00:00:00Z",
        ),
        ConflictReviewSide(
            assertion_id=uuid.uuid4(),
            source_type="EMR",
            speaker=Speaker.CLINICIAN,
            value="throat swelling",
            original_text="EMR note: throat swelling after penicillin",
            recorded_at="2024-09-28T00:00:00Z",
        ),
    ]


def _conflict_review(**overrides):
    defaults = dict(
        review_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        conflict_id=uuid.uuid4(),
        concept=ConceptReference(original_text="penicillin allergy", code="ALL-003"),
        sides=_conflict_review_sides(),
    )
    defaults.update(overrides)
    return ConflictReview(**defaults)


def test_conflict_review_requires_at_least_two_sides():
    with pytest.raises(ValidationError, match="at least two"):
        _conflict_review(sides=_conflict_review_sides()[:1])


def test_conflict_review_reconciled_requires_a_resolved_value():
    with pytest.raises(ValidationError, match="resolved_value"):
        _conflict_review(
            status=ContradictionStatus.RECONCILED,
            resolution={"resolved_by": "dr-smith", "rationale": "picked EMR"},
        )


def test_conflict_review_escalated_requires_a_resolution():
    with pytest.raises(ValidationError, match="ESCALATED requires"):
        _conflict_review(status=ContradictionStatus.ESCALATED)


def test_conflict_review_reconciled_succeeds_with_a_resolved_value():
    review = _conflict_review(
        status=ContradictionStatus.RECONCILED,
        resolution={
            "resolved_by": "dr-smith",
            "rationale": "EMR note is contemporaneous, patient recall is unreliable here",
            "resolved_value": "throat swelling",
        },
    )
    assert review.resolution.resolved_value == "throat swelling"


def test_conflict_review_escalated_succeeds_with_no_resolved_value():
    review = _conflict_review(
        status=ContradictionStatus.ESCALATED,
        resolution={"resolved_by": "dr-smith", "rationale": "neither side is trustworthy, needs specialist review"},
    )
    assert review.resolution.resolved_value is None
