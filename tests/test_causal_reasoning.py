import math

import pytest

from periop_core.causal_reasoning import (
    entropy,
    expected_clinical_discrimination,
    marginal_probability,
    normalise_confidences,
    posterior_given_answer,
)


def test_entropy_of_certain_distribution_is_zero():
    assert entropy({"a": 1.0}) == pytest.approx(0.0)


def test_entropy_of_fair_coin_is_one_bit():
    assert entropy({"a": 0.5, "b": 0.5}) == pytest.approx(1.0)


def test_entropy_of_four_equal_outcomes_is_two_bits():
    assert entropy({"a": 0.25, "b": 0.25, "c": 0.25, "d": 0.25}) == pytest.approx(2.0)


def test_entropy_rejects_distribution_not_summing_to_one():
    with pytest.raises(ValueError, match="sum to 1.0"):
        entropy({"a": 0.5, "b": 0.6})


def test_entropy_rejects_negative_probability():
    with pytest.raises(ValueError, match="negative"):
        entropy({"a": 1.5, "b": -0.5})


def test_perfectly_discriminating_question_has_ecd_equal_to_full_prior_entropy():
    prior = {"PE": 0.5, "MI": 0.5}
    likelihoods = {
        "yes": {"PE": 1.0, "MI": 0.0},
        "no": {"PE": 0.0, "MI": 1.0},
    }
    ecd = expected_clinical_discrimination(prior, likelihoods)
    assert ecd == pytest.approx(entropy(prior))
    assert ecd == pytest.approx(1.0)


def test_uninformative_question_has_zero_ecd():
    prior = {"PE": 0.5, "MI": 0.5}
    likelihoods = {
        "yes": {"PE": 0.5, "MI": 0.5},
        "no": {"PE": 0.5, "MI": 0.5},
    }
    ecd = expected_clinical_discrimination(prior, likelihoods)
    assert ecd == pytest.approx(0.0)


def test_partially_discriminating_question_has_intermediate_ecd():
    prior = {"PE": 0.5, "MI": 0.5}
    # A somewhat informative but imperfect question.
    likelihoods = {
        "yes": {"PE": 0.8, "MI": 0.3},
        "no": {"PE": 0.2, "MI": 0.7},
    }
    ecd = expected_clinical_discrimination(prior, likelihoods)
    assert 0.0 < ecd < 1.0


def test_posterior_updates_toward_more_likely_hypothesis():
    prior = {"PE": 0.5, "MI": 0.5}
    likelihood_row = {"PE": 0.9, "MI": 0.1}
    posterior = posterior_given_answer(prior, likelihood_row)
    assert posterior["PE"] > posterior["MI"]
    assert posterior["PE"] == pytest.approx(0.9)  # symmetric prior -> posterior = normalised likelihood


def test_marginal_probability_computation():
    prior = {"PE": 0.5, "MI": 0.5}
    likelihood_row = {"PE": 0.9, "MI": 0.1}
    assert marginal_probability(prior, likelihood_row) == pytest.approx(0.5)


def test_ecd_rejects_inconsistent_answer_space():
    prior = {"PE": 0.5, "MI": 0.5}
    # Marginals across answers must sum to 1; this doesn't.
    likelihoods = {
        "yes": {"PE": 0.5, "MI": 0.5},
    }
    with pytest.raises(ValueError, match="Answer likelihoods are inconsistent"):
        expected_clinical_discrimination(prior, likelihoods)


def test_normalise_confidences():
    normalised = normalise_confidences({"PE": 0.4, "MI": 0.2, "other": 0.2})
    assert sum(normalised.values()) == pytest.approx(1.0)
    assert normalised["PE"] == pytest.approx(0.5)


def test_normalise_confidences_rejects_all_zero():
    with pytest.raises(ValueError):
        normalise_confidences({"PE": 0.0, "MI": 0.0})
