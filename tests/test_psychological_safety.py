import uuid

import pytest

from periop_core.psychological_safety import initial_state, update


def test_initial_state_is_neutral():
    state = initial_state(uuid.uuid4())
    assert state.estimate == pytest.approx(0.5)
    assert state.evidence_signals


def test_positive_signal_increases_estimate():
    state = initial_state(uuid.uuid4())
    updated = update(state, ["patient_corrected_system_without_hesitation"])
    assert updated.estimate > state.estimate
    assert "patient_corrected_system_without_hesitation" in updated.evidence_signals


def test_negative_signal_decreases_estimate():
    state = initial_state(uuid.uuid4())
    updated = update(state, ["patient_showed_distress_when_correcting_system"])
    assert updated.estimate < state.estimate


def test_estimate_clamped_to_unit_interval():
    state = initial_state(uuid.uuid4())
    for _ in range(20):
        state = update(state, ["patient_corrected_system_without_hesitation"])
    assert state.estimate <= 1.0

    state2 = initial_state(uuid.uuid4())
    for _ in range(20):
        state2 = update(state2, ["system_error_went_unacknowledged"])
    assert state2.estimate >= 0.0


def test_unknown_signal_raises():
    state = initial_state(uuid.uuid4())
    with pytest.raises(KeyError):
        update(state, ["made_up_signal"])


def test_empty_signal_list_is_a_no_op():
    state = initial_state(uuid.uuid4())
    updated = update(state, [])
    assert updated == state
