import uuid

import pytest
from pydantic import ValidationError

from periop_core.enums import AssertionState, Certainty, ConflictType, Materiality, Speaker
from periop_core.models import Assertion, ConceptReference, Conflict, SourceReference, WorkingFact


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
