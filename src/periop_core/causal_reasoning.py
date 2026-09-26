"""Causal hypothesis reasoning support (Full Spec §6A.10).

'The Model Layer may maintain provisional causal hypotheses to support
discriminating questions. Temporal sequence, association and causation
must remain separate relations.'

    ECD(Q) = H(Hypotheses) - E[H(Hypotheses | Answer_Q)]

This is ordinary Shannon entropy / expected information gain, implemented
for real (not stubbed): given a prior distribution over candidate
CausalHypotheses and a likelihood model of how each candidate hypothesis
would generate each possible answer to a candidate question, this module
computes the expected reduction in uncertainty (in bits) that asking that
question would produce -- the "most discriminating question" is the one
with the highest ECD.

Scope honestly stated: this module does not *generate* the likelihood
model P(Answer | Hypothesis) -- that would require either clinical
domain knowledge encoded as a rules table or an LLM/statistical estimate,
neither of which exists in this MVP pass. It provides the entropy
machinery so that whichever component eventually supplies a likelihood
model (a future clinical rules pack, most plausibly) can be scored
correctly. `CausalHypothesis.status` never advances past HYPOTHESIS/
DISCRIMINATED from this module alone -- see periop_core.model_layer's
ADJUDICATED-requires-clinician-marker invariant.
"""
from __future__ import annotations

import math
from typing import Hashable, TypeVar

H = TypeVar("H", bound=Hashable)
A = TypeVar("A", bound=Hashable)

_PROBABILITY_SUM_TOLERANCE = 1e-6


def _check_distribution(distribution: dict[H, float], *, name: str) -> None:
    if not distribution:
        raise ValueError(f"{name} must not be empty")
    total = sum(distribution.values())
    if abs(total - 1.0) > _PROBABILITY_SUM_TOLERANCE:
        raise ValueError(f"{name} must sum to 1.0, got {total}")
    for key, p in distribution.items():
        if p < 0.0:
            raise ValueError(f"{name}[{key!r}] is negative ({p})")


def entropy(distribution: dict[H, float]) -> float:
    """Shannon entropy in bits. Zero-probability entries contribute 0
    (the standard 0*log(0) := 0 convention), and are otherwise validated
    as a proper probability distribution."""
    _check_distribution(distribution, name="distribution")
    return -sum(p * math.log2(p) for p in distribution.values() if p > 0.0)


def normalise_confidences(raw: dict[H, float]) -> dict[H, float]:
    """Turn a set of independent per-hypothesis confidences (as stored on
    CausalHypothesis.confidence, each in [0,1] but not necessarily
    summing to 1 across alternatives) into a proper prior distribution by
    normalising. Raises if all confidences are zero (nothing to
    normalise against)."""
    total = sum(raw.values())
    if total <= 0.0:
        raise ValueError("Cannot normalise a set of all-zero confidences")
    return {h: v / total for h, v in raw.items()}


def posterior_given_answer(
    prior: dict[H, float], likelihood_row: dict[H, float]
) -> dict[H, float]:
    """Bayes' rule: P(H | Answer=a) proportional to P(a | H) * P(H).

    `likelihood_row` is P(Answer=a | H) for the specific answer `a`,
    keyed by hypothesis, over the same hypothesis set as `prior`.
    """
    _check_distribution(prior, name="prior")
    missing = set(prior) - set(likelihood_row)
    if missing:
        raise ValueError(f"likelihood_row missing entries for hypotheses: {missing}")

    unnormalised = {h: likelihood_row[h] * prior[h] for h in prior}
    total = sum(unnormalised.values())
    if total <= 0.0:
        raise ValueError(
            "This answer has zero marginal probability under the prior/likelihood "
            "given (every P(answer|hypothesis)*prior term is zero)"
        )
    return {h: v / total for h, v in unnormalised.items()}


def marginal_probability(prior: dict[H, float], likelihood_row: dict[H, float]) -> float:
    """P(Answer=a) = sum_h P(a|h) * P(h)."""
    _check_distribution(prior, name="prior")
    missing = set(prior) - set(likelihood_row)
    if missing:
        raise ValueError(f"likelihood_row missing entries for hypotheses: {missing}")
    return sum(likelihood_row[h] * prior[h] for h in prior)


def expected_clinical_discrimination(
    prior: dict[H, float], likelihoods: dict[A, dict[H, float]]
) -> float:
    """ECD(Q) = H(prior) - E_a[H(posterior | a)].

    `likelihoods` maps each possible answer to Q to its likelihood row
    P(answer | hypothesis) over the same hypothesis set as `prior`. The
    answers' marginal probabilities are derived from `prior` and
    `likelihoods`, not supplied separately, so they are guaranteed
    consistent with the prior.
    """
    _check_distribution(prior, name="prior")
    if not likelihoods:
        raise ValueError("likelihoods must contain at least one possible answer")

    prior_entropy = entropy(prior)

    expected_posterior_entropy = 0.0
    total_marginal = 0.0
    for answer, likelihood_row in likelihoods.items():
        p_answer = marginal_probability(prior, likelihood_row)
        if p_answer <= 0.0:
            continue  # this answer cannot occur under the prior; contributes nothing
        posterior = posterior_given_answer(prior, likelihood_row)
        expected_posterior_entropy += p_answer * entropy(posterior)
        total_marginal += p_answer

    if abs(total_marginal - 1.0) > 1e-4:
        raise ValueError(
            f"Answer likelihoods are inconsistent: marginal probabilities summed "
            f"to {total_marginal}, expected 1.0. Check that `likelihoods` covers "
            f"the full outcome space for the question."
        )

    return prior_entropy - expected_posterior_entropy
