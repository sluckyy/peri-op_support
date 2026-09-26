import pytest

from periop_core.enums import SessionStatus
from periop_core.eligibility import EligibilityContext
from periop_core.models import ReleaseManifest
from periop_core.services.session_service import (
    SessionCreationRejected,
    acknowledge_ai_notice,
    activate_session,
    create_session,
)


def _manifest():
    return ReleaseManifest(
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


def _eligible_ctx():
    return EligibilityContext(
        age_years=45,
        age_source="booking_feed",
        is_obstetric_procedure=False,
        is_obstetric_source="booking_feed",
        is_emergency_listing=False,
        is_emergency_source="booking_feed",
    )


def test_create_session_rejected_for_ineligible_patient():
    ctx = _eligible_ctx()
    ctx.age_years = 15
    with pytest.raises(SessionCreationRejected):
        create_session(subject_ref="pt-1", manifest=_manifest(), eligibility_ctx=ctx)


def test_activate_requires_ai_notice_acknowledged_first():
    session = create_session(
        subject_ref="pt-1", manifest=_manifest(), eligibility_ctx=_eligible_ctx()
    )
    assert session.status == SessionStatus.INITIALISE

    with pytest.raises(ValueError, match="INV-017"):
        activate_session(session)


def test_full_happy_path_create_acknowledge_activate():
    session = create_session(
        subject_ref="pt-1", manifest=_manifest(), eligibility_ctx=_eligible_ctx()
    )
    session = acknowledge_ai_notice(session)
    session = activate_session(session)

    assert session.status == SessionStatus.ACTIVE
    assert session.notice_acknowledged_at is not None
