from periop_core.enums import EligibilityResult
from periop_core.eligibility import EligibilityContext, evaluate_eligibility


def _ctx(**overrides):
    defaults = dict(
        age_years=45,
        age_source="booking_feed",
        is_obstetric_procedure=False,
        is_obstetric_source="booking_feed",
        is_emergency_listing=False,
        is_emergency_source="booking_feed",
    )
    defaults.update(overrides)
    return EligibilityContext(**defaults)


def test_eligible_adult_elective_patient():
    decision = evaluate_eligibility(_ctx())
    assert decision.result == EligibilityResult.ELIGIBLE
    assert decision.reasons == []


def test_underage_patient_is_ineligible():
    decision = evaluate_eligibility(_ctx(age_years=16, age_source="self_declared"))
    assert decision.result == EligibilityResult.INELIGIBLE
    assert any("18" in r for r in decision.reasons)


def test_obstetric_flag_is_ineligible():
    decision = evaluate_eligibility(_ctx(is_obstetric_procedure=True))
    assert decision.result == EligibilityResult.INELIGIBLE


def test_emergency_listing_is_ineligible():
    decision = evaluate_eligibility(_ctx(is_emergency_listing=True))
    assert decision.result == EligibilityResult.INELIGIBLE


def test_unknown_age_is_ineligible_not_silently_assumed_eligible():
    decision = evaluate_eligibility(_ctx(age_years=None, age_source="unavailable"))
    assert decision.result == EligibilityResult.INELIGIBLE
