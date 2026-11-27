"""Unit tests for periop_core.interview_llm (LLM-001 / LLM-003 and their
deterministic validators). No network, no DB -- see tests/fake_llm.py."""
import anthropic
import httpx2
import pytest

from periop_core.enums import AssertionState, Certainty
from periop_core.interview_llm import (
    ExtractionCandidate,
    InterviewerUnavailable,
    extract_answer,
    realise_question,
    validate_candidate,
    validate_utterance,
)
from tests.fake_llm import FakeLLM

EXTRACT_ARGS = dict(
    concept_label="Limited mouth opening",
    clinical_definition="Reduced mouth opening that may affect airway access",
    question="Do you have difficulty opening your mouth widely?",
    response_type="boolean",
    transcript="yeah a bit, my jaw clicks and gets stuck",
)


def _candidate(**overrides):
    base = dict(answered=True, assertion_state="AFFIRMED", value="jaw clicks and gets stuck",
                explicit=True, needs_clarification=False)
    base.update(overrides)
    return base


# ------------------------------------------------------------- extraction

def test_extract_answer_parses_structured_output():
    llm = FakeLLM([_candidate()])
    result = extract_answer(llm, **EXTRACT_ARGS)
    assert result.assertion_state == AssertionState.AFFIRMED
    assert result.value == "jaw clicks and gets stuck"
    call = llm.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["output_config"]["effort"] == "low"
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert call["fallbacks"] == "default"
    assert EXTRACT_ARGS["transcript"] in call["messages"][0]["content"]


def test_extract_answer_retries_once_on_bad_schema_then_succeeds():
    llm = FakeLLM(["not json at all", _candidate(assertion_state="NEGATED")])
    result = extract_answer(llm, **EXTRACT_ARGS)
    assert result.assertion_state == AssertionState.NEGATED
    assert len(llm.calls) == 2


def test_extract_answer_fails_closed_after_two_bad_outputs():
    llm = FakeLLM([{"answered": "maybe"}, "{}"])
    with pytest.raises(InterviewerUnavailable):
        extract_answer(llm, **EXTRACT_ARGS)


def test_extract_answer_without_client_fails_closed():
    with pytest.raises(InterviewerUnavailable):
        extract_answer(None, **EXTRACT_ARGS)


def test_extract_answer_refusal_fails_closed():
    llm = FakeLLM([_candidate()], stop_reason="refusal")
    with pytest.raises(InterviewerUnavailable):
        extract_answer(llm, **EXTRACT_ARGS)


def test_extract_answer_connection_error_fails_closed():
    err = anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages"))
    with pytest.raises(InterviewerUnavailable):
        extract_answer(FakeLLM([err]), **EXTRACT_ARGS)


def test_model_is_configurable_and_fallbacks_only_where_supported(monkeypatch):
    monkeypatch.setenv("PERIOP_LLM_MODEL", "claude-haiku-4-5")
    llm = FakeLLM([_candidate()])
    extract_answer(llm, **EXTRACT_ARGS)
    assert llm.calls[0]["model"] == "claude-haiku-4-5"
    assert "fallbacks" not in llm.calls[0]


# ------------------------------------------------------------- validator

def test_validate_candidate_pins_the_asked_concept():
    answer = validate_candidate(ExtractionCandidate(**_candidate()), "AIR-001")
    assert answer.concept_code == "AIR-001"
    assert answer.certainty == Certainty.EXPLICIT


def test_validate_candidate_maps_inferred_and_uncertain_certainty():
    inferred = validate_candidate(ExtractionCandidate(**_candidate(explicit=False)), "AIR-001")
    assert inferred.certainty == Certainty.INFERRED_MODERATE
    unsure = validate_candidate(
        ExtractionCandidate(**_candidate(assertion_state="UNCERTAIN", explicit=True)), "AIR-001"
    )
    assert unsure.assertion_state == AssertionState.UNCERTAIN
    assert unsure.certainty == Certainty.INFERRED_LOW


@pytest.mark.parametrize("overrides", [dict(answered=False), dict(needs_clarification=True)])
def test_validate_candidate_records_nothing_when_unclear(overrides):
    assert validate_candidate(ExtractionCandidate(**_candidate(**overrides)), "AIR-001") is None


def test_validate_candidate_blank_value_becomes_none():
    answer = validate_candidate(ExtractionCandidate(**_candidate(value="  ")), "AIR-001")
    assert answer.value is None


# ------------------------------------------------------------- realisation

REALISE_ARGS = dict(
    patient_question="Do you have difficulty opening your mouth widely?",
    concept_label="Limited mouth opening",
    domain="Airway, dental and anatomical history",
    previous_recorded=True,
)


def test_realise_question_uses_validated_llm_phrasing():
    llm = FakeLLM([{"utterance": "Thanks. Do you ever find it hard to open your mouth wide?"}])
    text, by_llm = realise_question(llm, **REALISE_ARGS)
    assert by_llm is True
    assert text.endswith("?")


@pytest.mark.parametrize("bad", [
    "",
    "Do you have trouble opening your mouth? Or chewing?",
    "Tell me about your mouth.",
    "Don't worry, this is routine. Can you open your mouth widely?",
    "x" * 400 + "?",
])
def test_realise_question_rejects_bad_output_and_falls_back(bad):
    text, by_llm = realise_question(FakeLLM([{"utterance": bad}]), **REALISE_ARGS)
    assert by_llm is False
    assert text == REALISE_ARGS["patient_question"]


def test_realise_question_falls_back_on_api_error_and_without_client():
    err = anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages"))
    assert realise_question(FakeLLM([err]), **REALISE_ARGS) == (REALISE_ARGS["patient_question"], False)
    assert realise_question(None, **REALISE_ARGS) == (REALISE_ARGS["patient_question"], False)


def test_reask_always_uses_the_apology_template_without_calling_the_model():
    llm = FakeLLM([])
    text, by_llm = realise_question(llm, **{**REALISE_ARGS, "reask": True})
    assert text == "Sorry, I didn't quite catch that. " + REALISE_ARGS["patient_question"]
    assert by_llm is False
    assert llm.calls == []


def test_validate_utterance_accepts_a_plain_question():
    assert validate_utterance("Okay, now about your heart. Do you have high blood pressure?")
