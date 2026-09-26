import pytest

from periop_core.attention import (
    DEFAULT_WEIGHTS,
    AttentionCandidate,
    AttentionFactors,
    attention_score,
    select_working_set,
)


def test_factors_out_of_range_rejected():
    with pytest.raises(ValueError):
        AttentionFactors(risk=1.5)
    with pytest.raises(ValueError):
        AttentionFactors(topic_distance=-0.1)


def test_higher_risk_scores_higher_all_else_equal():
    low_risk = AttentionFactors(risk=0.1, clinical_value=0.5)
    high_risk = AttentionFactors(risk=0.9, clinical_value=0.5)
    assert attention_score(high_risk) > attention_score(low_risk)


def test_topic_distance_reduces_score():
    near = AttentionFactors(clinical_value=0.5, topic_distance=0.0)
    far = AttentionFactors(clinical_value=0.5, topic_distance=1.0)
    assert attention_score(near) > attention_score(far)


def test_working_set_respects_max_size_without_high_risk_items():
    candidates = [
        AttentionCandidate(item=f"item-{i}", factors=AttentionFactors(clinical_value=score))
        for i, score in enumerate([0.9, 0.7, 0.5, 0.3, 0.1])
    ]
    result = select_working_set(candidates, max_size=2)
    assert result.working_set == ["item-0", "item-1"]
    assert result.forced_inclusions == []


def test_high_risk_item_force_included_beyond_max_size():
    # Force-inclusion is checked on the raw risk *factor*, independent of
    # how heavily risk is weighted in the ranking score -- so here we use
    # a weighting that would otherwise bury the risky item at the bottom
    # of the ranking, to isolate that the force-include path is what
    # rescues it rather than it winning on score alone.
    low_risk_weight = {**DEFAULT_WEIGHTS, "risk": 0.01}
    candidates = [
        AttentionCandidate(item="high-priority-a", factors=AttentionFactors(clinical_value=0.9)),
        AttentionCandidate(item="high-priority-b", factors=AttentionFactors(clinical_value=0.8)),
        AttentionCandidate(
            item="unresolved-critical-allergy",
            factors=AttentionFactors(risk=0.95, clinical_value=0.01),
        ),
    ]
    scores = {
        c.item: attention_score(c.factors, low_risk_weight) for c in candidates
    }
    assert scores["unresolved-critical-allergy"] < scores["high-priority-b"], (
        "test setup invalid: the risky item must rank last on score alone"
    )

    result = select_working_set(candidates, max_size=2, weights=low_risk_weight)
    assert "unresolved-critical-allergy" in result.working_set
    assert "unresolved-critical-allergy" in result.forced_inclusions
    assert len(result.working_set) == 3


def test_empty_candidates_returns_empty_working_set():
    result = select_working_set([], max_size=5)
    assert result.working_set == []
    assert result.forced_inclusions == []
