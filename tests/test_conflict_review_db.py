"""Round-trip tests for periop_core.conflict_review_db against a real
Postgres instance (see conftest.py -- skipped if none is reachable).
"""
import uuid
from datetime import datetime, timezone

import pytest

from periop_core.conflict_review_db import (
    get_conflict_review,
    insert_conflict_review,
    list_conflict_reviews,
    update_conflict_review_resolution,
)
from periop_core.db import insert_release_manifest, insert_session
from periop_core.enums import ContradictionStatus, Speaker
from periop_core.models import (
    ConceptReference,
    ConflictResolution,
    ConflictReview,
    ConflictReviewSide,
    ReleaseManifest,
    Session,
)


def _session(conn):
    manifest = ReleaseManifest(
        clinical_dataset_version="1.0.1",
        rules_version="0.1.0",
        terminology_version="unpinned",
        prompt_version="0.1.0",
        extractor_model_id="none",
        language_model_id="none",
        validator_version="0.1.0",
        fhir_mapping_version="0.1.0",
        site_configuration_version="dev",
    )
    insert_release_manifest(conn, manifest)
    session = Session(subject_ref="pt-1", manifest_id=manifest.manifest_id)
    insert_session(conn, session)
    return session


def _sides():
    now = datetime.now(timezone.utc)
    return [
        ConflictReviewSide(
            assertion_id=uuid.uuid4(),
            source_type="PATIENT",
            speaker=Speaker.PATIENT,
            value="no reaction",
            original_text="patient says no reaction at all",
            recorded_at=now,
        ),
        ConflictReviewSide(
            assertion_id=uuid.uuid4(),
            source_type="EMR",
            speaker=Speaker.CLINICIAN,
            value="throat swelling",
            original_text="EMR note: throat swelling after penicillin",
            recorded_at=now,
        ),
    ]


def test_conflict_review_round_trip(db_conn):
    session = _session(db_conn)
    review = ConflictReview(
        review_id=uuid.uuid4(),
        session_id=session.session_id,
        conflict_id=uuid.uuid4(),
        concept=ConceptReference(original_text="penicillin allergy", code="ALL-003"),
        sides=_sides(),
    )
    insert_conflict_review(db_conn, review)

    fetched = get_conflict_review(db_conn, review.review_id)
    assert fetched.status == ContradictionStatus.OPEN
    assert fetched.resolution is None
    assert len(fetched.sides) == 2
    assert fetched.sides[0].source_type == "PATIENT"

    listed = list_conflict_reviews(db_conn, session.session_id)
    assert len(listed) == 1
    assert listed[0].review_id == review.review_id


def test_conflict_review_resolution_round_trip(db_conn):
    session = _session(db_conn)
    review = ConflictReview(
        review_id=uuid.uuid4(),
        session_id=session.session_id,
        conflict_id=uuid.uuid4(),
        concept=ConceptReference(original_text="penicillin allergy", code="ALL-003"),
        sides=_sides(),
    )
    insert_conflict_review(db_conn, review)

    resolved = review.model_copy(
        update={
            "status": ContradictionStatus.RECONCILED,
            "resolution": ConflictResolution(
                resolved_by="dr-smith",
                rationale="EMR note is from the same admission, patient recall is unreliable here",
                resolved_value="throat swelling",
            ),
        }
    )
    update_conflict_review_resolution(db_conn, resolved)

    refetched = get_conflict_review(db_conn, review.review_id)
    assert refetched.status == ContradictionStatus.RECONCILED
    assert refetched.resolution.resolved_by == "dr-smith"
    assert refetched.resolution.resolved_value == "throat swelling"


def test_get_conflict_review_missing_raises_keyerror(db_conn):
    with pytest.raises(KeyError):
        get_conflict_review(db_conn, uuid.uuid4())
