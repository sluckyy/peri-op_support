from periop_core.humour_policy import (
    HumourContext,
    HumourUtilityFactors,
    humour_utility,
    is_humour_permitted,
)


def test_disabled_by_default():
    permitted, reasons = is_humour_permitted(HumourContext())
    assert permitted is False
    assert any("off by default" in r for r in reasons)


def test_patient_directed_humour_always_prohibited_even_when_enabled():
    ctx = HumourContext(feature_enabled=True, proposed_target="patient", receptivity_known=True)
    permitted, reasons = is_humour_permitted(ctx)
    assert permitted is False
    assert any("prohibited outright" in r for r in reasons)


def test_suppressed_during_high_distress_even_when_enabled():
    ctx = HumourContext(feature_enabled=True, receptivity_known=True, high_distress=True)
    permitted, _ = is_humour_permitted(ctx)
    assert permitted is False


def test_suppressed_when_receptivity_unknown():
    ctx = HumourContext(feature_enabled=True, receptivity_known=False)
    permitted, reasons = is_humour_permitted(ctx)
    assert permitted is False
    assert any("receptivity uncertain" in r for r in reasons)


def test_permitted_when_enabled_and_no_suppression_conditions():
    ctx = HumourContext(feature_enabled=True, proposed_target="self", receptivity_known=True)
    permitted, reasons = is_humour_permitted(ctx)
    assert permitted is True
    assert reasons == ["no suppression condition triggered and feature enabled"]


def test_self_deprecation_implying_incompetence_suppressed():
    ctx = HumourContext(
        feature_enabled=True,
        receptivity_known=True,
        proposed_target="self",
        implies_incompetence=True,
    )
    permitted, reasons = is_humour_permitted(ctx)
    assert permitted is False
    assert any("imply incompetence" in r for r in reasons)


def test_humour_utility_additive_formula():
    factors = HumourUtilityFactors(
        rapport=0.5,
        affiliation=0.3,
        tension_reduction=0.2,
        status_reduction=0.1,
        misinterpretation_risk=0.4,
        inappropriateness_risk=0.1,
        competence_loss_risk=0.0,
    )
    assert humour_utility(factors) == 0.5 + 0.3 + 0.2 + 0.1 - 0.4 - 0.1 - 0.0
