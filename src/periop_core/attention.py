"""Attention / bounded working-memory selection (Full Spec §6A.5).

'The Model Layer must not treat every prior statement as equally
salient. It creates a bounded working conversational state from
clinically relevant, unresolved and patient-salient items while retaining
other information for context-sensitive retrieval.'

    Attention_i(t) = f(Risk, Uncertainty, ClinicalValue, PatientSalience,
                        Emotion, GoalRelevance, Deadline, TriggerMatch,
                        TopicDistance, Recency)

Scope honestly stated: `f` is implemented here as a deterministic,
configurable weighted sum -- not a learned function. That is a reasonable
MVP interpretation (the spec does not mandate a specific functional form)
but the weights below are a starting point, not a validated/calibrated
set. The output is a comparative ranking score, not a probability.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

_FACTOR_NAMES = (
    "risk",
    "uncertainty",
    "clinical_value",
    "patient_salience",
    "emotion",
    "goal_relevance",
    "deadline_proximity",
    "trigger_match",
    "recency",
)


@dataclass(frozen=True)
class AttentionFactors:
    """All factors normalised to [0, 1]. `topic_distance` is a cost (how
    far the item is from the current conversational focus) and is
    subtracted rather than added -- everything else is a boost."""

    risk: float = 0.0
    uncertainty: float = 0.0
    clinical_value: float = 0.0
    patient_salience: float = 0.0
    emotion: float = 0.0
    goal_relevance: float = 0.0
    deadline_proximity: float = 0.0
    trigger_match: float = 0.0
    topic_distance: float = 0.0
    recency: float = 0.0

    def __post_init__(self) -> None:
        for name in (*_FACTOR_NAMES, "topic_distance"):
            value = getattr(self, name)
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"AttentionFactors.{name} must be in [0, 1], got {value}")


DEFAULT_WEIGHTS: dict[str, float] = {
    "risk": 3.0,
    "uncertainty": 1.0,
    "clinical_value": 2.0,
    "patient_salience": 1.5,
    "emotion": 1.0,
    "goal_relevance": 1.0,
    "deadline_proximity": 1.5,
    "trigger_match": 2.0,
    "topic_distance": 1.0,  # cost weight -- subtracted
    "recency": 0.5,
}

# Above this raw `risk` factor, an item is treated as safety-critical and
# is force-included in the working set regardless of max_size (6A.5:
# "High-risk unresolved obligations remain persistent until resolved or
# handed off").
DEFAULT_FORCE_INCLUDE_RISK_THRESHOLD = 0.85


def attention_score(
    factors: AttentionFactors, weights: dict[str, float] = DEFAULT_WEIGHTS
) -> float:
    boost = sum(weights.get(name, 0.0) * getattr(factors, name) for name in _FACTOR_NAMES)
    cost = weights.get("topic_distance", 0.0) * factors.topic_distance
    return boost - cost


T = TypeVar("T")


@dataclass(frozen=True)
class AttentionCandidate(Generic[T]):
    item: T
    factors: AttentionFactors


@dataclass(frozen=True)
class WorkingSetResult(Generic[T]):
    working_set: list[T]
    forced_inclusions: list[T]
    scores: dict[int, float] = field(default_factory=dict)  # id(item) -> score, for inspection


def select_working_set(
    candidates: list[AttentionCandidate[T]],
    max_size: int,
    *,
    weights: dict[str, float] = DEFAULT_WEIGHTS,
    force_include_risk_threshold: float = DEFAULT_FORCE_INCLUDE_RISK_THRESHOLD,
) -> WorkingSetResult[T]:
    """Rank candidates by attention_score and take the top `max_size`,
    but always force-include any candidate whose risk factor exceeds
    `force_include_risk_threshold` even if that pushes the result above
    max_size -- a high-risk unresolved item must not be dropped from
    working memory purely for being outranked (6A.5).
    """
    scored = [(c, attention_score(c.factors, weights)) for c in candidates]
    scored.sort(key=lambda pair: pair[1], reverse=True)

    forced = [c for c, _ in scored if c.factors.risk > force_include_risk_threshold]
    ranked_items = [c for c, _ in scored]

    working: list[AttentionCandidate[T]] = []
    for c in ranked_items:
        if c in forced:
            if c not in working:
                working.append(c)
            continue
        if len(working) < max_size:
            working.append(c)

    # Preserve rank order in the final list.
    working_sorted = [c for c in ranked_items if c in working]

    return WorkingSetResult(
        working_set=[c.item for c in working_sorted],
        forced_inclusions=[c.item for c in forced],
        scores={id(c.item): score for c, score in scored},
    )
