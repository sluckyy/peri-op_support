"""The two bounded LLM calls behind the conversational interviewer
(Full Spec §10.2), each wrapped in a deterministic validator:

- LLM-001 turn extraction: patient words -> a *candidate* answer for the
  one concept that was asked. Clinical authority: none. The concept is
  pinned by the caller, never chosen by the model, and nothing reaches
  the assertion store without passing `validate_candidate`.
- LLM-003 question realisation: an InterviewAction's patient question ->
  natural spoken phrasing. Input is the action contract only (no clinical
  facts). Any validator failure or API error falls back to the dataset's
  question verbatim, so this path never blocks the interview.

Extraction failures fail closed (InterviewerUnavailable) -> the API
returns 503 and the UI drops to the manual form, per the addendum's
"single provider, fail-closed to human handoff".
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Protocol

import anthropic
from pydantic import BaseModel, ValidationError

from periop_core.enums import AssertionState, Certainty

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-5-5"
PROMPT_VERSION = "interview-0.1.0"
MAX_QUESTION_CHARS = 300

# Models that accept server-side refusal fallback in its "default" form.
_FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}
_FALLBACK_BETA = "server-side-fallback-2026-07-01"

# LLM-003 must never stray into clinician-owned territory (spec §1: the
# system never declares a patient fit/cleared/safe, never diagnoses).
PROHIBITED_PHRASES = (
    "diagnos",
    "fit for surgery",
    "safe for surgery",
    "safe to proceed",
    "cleared for",
    "you should stop",
    "you should start",
    "don't worry",
    "nothing to worry",
)


def llm_model() -> str:
    return os.environ.get("PERIOP_LLM_MODEL", DEFAULT_MODEL)


class InterviewerUnavailable(RuntimeError):
    """The extraction call could not produce a valid candidate after one
    schema retry (or the API is unreachable / refused). Fail closed."""


class _MessagesAPI(Protocol):
    def create(self, **kwargs: Any) -> Any: ...


class _BetaAPI(Protocol):
    messages: _MessagesAPI


class LLMClient(Protocol):
    beta: _BetaAPI


# ---------------------------------------------------------------- LLM-001

class ExtractionCandidate(BaseModel):
    answered: bool
    assertion_state: AssertionState
    value: str
    explicit: bool
    needs_clarification: bool


_EXTRACTION_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "answered": {"type": "boolean"},
        "assertion_state": {"type": "string", "enum": [s.value for s in AssertionState]},
        "value": {"type": "string"},
        "explicit": {"type": "boolean"},
        "needs_clarification": {"type": "boolean"},
    },
    "required": ["answered", "assertion_state", "value", "explicit", "needs_clarification"],
    "additionalProperties": False,
}

_EXTRACTION_SYSTEM = """\
You interpret one spoken answer from a patient during a pre-operative \
health questionnaire. You are given the single question that was asked, \
what it means clinically, and a transcript of the patient's reply (speech \
recognition may contain small errors). Return a candidate answer for that \
question only. You are not making clinical decisions; a clinician reviews \
everything.

Fields:
- answered: true if the reply actually addresses the question (including \
"I don't know" or "I'd rather not say"); false if it is off-topic, a \
question back, or unintelligible.
- assertion_state: AFFIRMED (yes / the thing is present / a concrete \
answer was given), NEGATED (clearly no / absent), UNCERTAIN (patient is \
unsure or hedging), UNKNOWN (patient says they don't know), DECLINED \
(patient chooses not to answer), CONDITIONAL (only under some \
circumstances, e.g. "only when I climb stairs").
- value: a short, faithful paraphrase of the substance of the answer in \
plain clinical English (for free-text questions this is the answer \
itself, e.g. "left knee replacement"; for yes/no questions add any \
detail given, or empty string if none). Never add facts the patient did \
not say.
- explicit: true if the patient stated it directly; false if you had to \
infer it.
- needs_clarification: true if the reply is too ambiguous to record and \
the question should be asked again.

Hard rules: uncertainty is never converted into a negative. If the \
patient is unsure, use UNCERTAIN or UNKNOWN, not NEGATED. If answered is \
false, set needs_clarification to true."""


@dataclass(frozen=True)
class ValidatedAnswer:
    concept_code: str
    assertion_state: AssertionState
    value: str | None
    certainty: Certainty


def _call(client: LLMClient, *, system: str, user: str, schema: dict[str, object],
          max_tokens: int) -> dict[str, Any]:
    """One structured-output call. Raises InterviewerUnavailable on API
    errors or refusal; raises ValueError on unparseable output (so the
    caller can apply its own retry/fallback policy)."""
    model = llm_model()
    kwargs: dict[str, Any] = dict(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
    )
    if model in _FALLBACK_MODELS:
        kwargs["betas"] = [_FALLBACK_BETA]
        kwargs["fallbacks"] = "default"
    try:
        response = client.beta.messages.create(**kwargs)
    except anthropic.APIStatusError as exc:
        log.warning("interviewer LLM call failed: HTTP %s (request %s)", exc.status_code,
                    getattr(exc, "request_id", None))
        raise InterviewerUnavailable(f"LLM API error {exc.status_code}") from exc
    except anthropic.APIConnectionError as exc:
        log.warning("interviewer LLM unreachable: %s", exc)
        raise InterviewerUnavailable("LLM API unreachable") from exc

    if response.stop_reason == "refusal":
        raise InterviewerUnavailable("LLM declined the request")
    if response.stop_reason == "max_tokens":
        raise ValueError("output truncated at max_tokens")
    text = next((b.text for b in response.content if getattr(b, "type", None) == "text"), None)
    if text is None:
        raise ValueError("no text block in response")
    return json.loads(text)


def extract_answer(
    client: LLMClient | None,
    *,
    concept_label: str,
    clinical_definition: str,
    question: str,
    response_type: str,
    transcript: str,
    recent_turns: list[tuple[str, str]] | None = None,
) -> ExtractionCandidate:
    """LLM-001. `recent_turns` is bounded context as (speaker, text) pairs
    -- the caller limits it to this question's own exchange."""
    if client is None:
        raise InterviewerUnavailable("no LLM client configured (ANTHROPIC_API_KEY unset)")

    context = ""
    if recent_turns:
        context = "Earlier in this exchange:\n" + "\n".join(
            f"{speaker}: {text}" for speaker, text in recent_turns
        ) + "\n\n"
    user = (
        f"Question asked: {question}\n"
        f"Concept: {concept_label}\n"
        f"Clinical meaning: {clinical_definition or concept_label}\n"
        f"Expected response type: {response_type or 'text'}\n\n"
        f"{context}"
        f"Patient's reply (transcript): {transcript}"
    )

    last_error: Exception | None = None
    for _attempt in range(2):  # spec LLM-001 fallback: schema retry, then human/modality fallback
        try:
            raw = _call(client, system=_EXTRACTION_SYSTEM, user=user,
                        schema=_EXTRACTION_SCHEMA, max_tokens=4096)
            return ExtractionCandidate.model_validate(raw)
        except (ValueError, ValidationError) as exc:
            last_error = exc
            log.warning("LLM-001 output failed schema validation: %s", exc)
    raise InterviewerUnavailable("extraction output failed validation twice") from last_error


def validate_candidate(candidate: ExtractionCandidate, concept_code: str) -> ValidatedAnswer | None:
    """Deterministic gate between LLM-001 and the assertion store. Returns
    None when nothing should be recorded (unanswered / needs clarification).
    The concept is always the one the caller asked about -- the model's
    output has no field that could redirect it."""
    if not candidate.answered or candidate.needs_clarification:
        return None
    state = candidate.assertion_state
    if state in (AssertionState.UNCERTAIN, AssertionState.UNKNOWN):
        certainty = Certainty.INFERRED_LOW
    elif candidate.explicit:
        certainty = Certainty.EXPLICIT
    else:
        certainty = Certainty.INFERRED_MODERATE
    value = candidate.value.strip() or None
    return ValidatedAnswer(concept_code=concept_code, assertion_state=state,
                           value=value, certainty=certainty)


# ---------------------------------------------------------------- LLM-003

_REALISATION_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {"utterance": {"type": "string"}},
    "required": ["utterance"],
    "additionalProperties": False,
}

_REALISATION_SYSTEM = """\
You are the voice of a friendly pre-operative health questionnaire, \
speaking to a patient. Rephrase the given question so it sounds natural \
when read aloud. Keep its exact meaning and ask exactly one question, \
ending with a question mark. Keep it under 40 words. You may open with a \
very short, neutral link from the previous answer (e.g. "Thanks." or \
"Okay, now about your heart."). Never give medical advice, reassurance, \
opinions about fitness for surgery, or diagnoses, and never mention \
anything about the patient that is not in the question itself."""


def template_question(patient_question: str, *, reask: bool = False) -> str:
    if reask:
        return f"Sorry, I didn't quite catch that. {patient_question}"
    return patient_question


def validate_utterance(text: str) -> bool:
    stripped = text.strip()
    if not stripped or len(stripped) > MAX_QUESTION_CHARS:
        return False
    if not stripped.endswith("?") or stripped.count("?") != 1:
        return False
    lowered = stripped.lower()
    return not any(p in lowered for p in PROHIBITED_PHRASES)


def realise_question(
    client: LLMClient | None,
    *,
    patient_question: str,
    concept_label: str,
    domain: str,
    previous_recorded: bool | None,
    reask: bool = False,
) -> tuple[str, bool]:
    """LLM-003. Returns (utterance, realised_by_llm). Falls back to the
    dataset question on any error or validator rejection."""
    fallback = template_question(patient_question, reask=reask)
    # A re-ask must unmistakably say the answer wasn't understood, so it
    # is always the fixed template rather than model phrasing.
    if client is None or reask:
        return fallback, False
    if previous_recorded is None:
        situation = "This is the first question of the interview; open with a brief greeting."
    else:
        situation = "The patient has just answered the previous question."
    user = (
        f"{situation}\n"
        f"Topic area: {domain}\n"
        f"Concept: {concept_label}\n"
        f"Question to ask: {patient_question}"
    )
    try:
        raw = _call(client, system=_REALISATION_SYSTEM, user=user,
                    schema=_REALISATION_SCHEMA, max_tokens=2048)
        utterance = str(raw.get("utterance", "")).strip() if isinstance(raw, dict) else ""
    except (InterviewerUnavailable, ValueError) as exc:
        log.info("LLM-003 fell back to template: %s", exc)
        return fallback, False
    if not validate_utterance(utterance):
        log.info("LLM-003 output rejected by validator: %r", utterance)
        return fallback, False
    return utterance, True
