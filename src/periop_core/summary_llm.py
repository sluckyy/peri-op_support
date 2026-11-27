"""LLM-005 clinician summary drafting (Full Spec §10.2): a short narrative
drafted from the deterministic ClinicalSummary only. Clinical authority:
draft only; fallback: the structured view, which is always shown.

The validator is deterministic and fails closed:
- SB-019: the draft must not claim review/acceptance or state fitness.
- No diagnoses or treatment recommendations (clinician-owned decisions).
- "No hidden critical issue": every item in the summary's attention list
  must be mentioned by name, or the draft is rejected.
Limitation stated honestly: it cannot prove the draft adds no fact absent
from its input; the prompt forbids that, the structured view stays the
record, and the draft is labelled as an unreviewed AI draft.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from pydantic import BaseModel

from periop_core.clinical_summary import ClinicalSummary
from periop_core.interview_llm import InterviewerUnavailable, LLMClient, llm_model, structured_call

PROMPT_VERSION = "summary-draft-0.1.0"
MAX_NARRATIVE_CHARS = 2500
DRAFT_LABEL = "AI DRAFT — not reviewed by a clinician"

PROHIBITED_PHRASES = (
    "fit for", "fitness for", "cleared for", "safe to proceed", "safe for surgery",
    "low risk", "high risk", "reviewed by", "approved by", "accepted by", "has been reviewed",
    "diagnos", "recommend", "should be given", "should stop", "should start", "should continue",
)

_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {"narrative": {"type": "string"}},
    "required": ["narrative"],
    "additionalProperties": False,
}

_SYSTEM = """\
You draft a short pre-operative handover note for an anaesthetist from \
structured data an AI interviewer collected from a patient. Write in \
plain clinical English, 120-250 words, as two or three short paragraphs: \
first anything flagged as needing attention (name every one), then the \
relevant positive findings, then notable gaps. Use only facts in the \
data; never add, infer or embellish. Say "patient reports" for \
patient-reported findings. Do not state or imply fitness for surgery, \
risk level, a diagnosis or any treatment recommendation, and do not say \
the information has been reviewed or verified by a clinician."""


class SummaryDraft(BaseModel):
    available: bool
    narrative: str | None = None
    reason: str | None = None
    label: str = DRAFT_LABEL
    model: str | None = None
    prompt_version: str = PROMPT_VERSION
    generated_at: datetime


def required_mentions(summary: ClinicalSummary) -> list[str]:
    mentions = []
    for item in summary.attention:
        if item.concept:
            mentions.append(item.concept)
        elif item.kind == "closure_block":
            mentions.append("closure")
    return list(dict.fromkeys(mentions))


def validate_narrative(text: str, summary: ClinicalSummary) -> str | None:
    """None if acceptable, otherwise the reason it was rejected."""
    stripped = text.strip()
    if not stripped:
        return "empty draft"
    if len(stripped) > MAX_NARRATIVE_CHARS:
        return "draft too long"
    lowered = stripped.lower()
    for phrase in PROHIBITED_PHRASES:
        if phrase in lowered:
            return f"draft used prohibited language ({phrase!r})"
    missing = [m for m in required_mentions(summary) if m.lower() not in lowered]
    if missing:
        return "draft omitted flagged item(s): " + ", ".join(missing)
    return None


def _prompt_data(summary: ClinicalSummary) -> str:
    def finding(f):
        return {"concept": f.concept, "answer": f.answer, "status": f.verification,
                "patient_words": [s.said for s in f.sources if s.speaker == "PATIENT"]}

    data = {
        "needs_attention": [
            {"title": a.title, "severity": a.severity, "detail": a.detail} for a in summary.attention
        ],
        "safety_critical_findings": [finding(f) for f in summary.safety_findings],
        "findings_by_system": [
            {"system": d.domain,
             "positive": [finding(f) for f in d.positives],
             "unsure": [finding(f) for f in d.unsure],
             "denies": [f.concept for f in d.negatives]}
            for d in summary.domains
        ],
        "mandatory_questions_unanswered": [u.concept for u in summary.unanswered_mandatory],
        "counts": summary.counts.model_dump(),
    }
    return json.dumps(data, indent=1, default=str)


def draft_summary(client: LLMClient | None, summary: ClinicalSummary) -> SummaryDraft:
    now = datetime.now(timezone.utc)
    if client is None:
        return SummaryDraft(available=False, reason="AI drafting is not configured", generated_at=now)
    user = "Structured summary data:\n" + _prompt_data(summary)
    must = required_mentions(summary)
    if must:
        user += "\n\nYou must mention each of these by name: " + "; ".join(must)
    reason = "draft failed validation"
    for _attempt in range(2):
        try:
            raw = structured_call(client, system=_SYSTEM, user=user, schema=_SCHEMA,
                                  max_tokens=8000, effort="medium")
        except InterviewerUnavailable as exc:
            return SummaryDraft(available=False, reason=f"AI drafting unavailable ({exc})", generated_at=now)
        except ValueError:
            reason = "draft output was malformed"
            continue
        narrative = str(raw.get("narrative", "")) if isinstance(raw, dict) else ""
        problem = validate_narrative(narrative, summary)
        if problem is None:
            return SummaryDraft(available=True, narrative=narrative.strip(), model=llm_model(), generated_at=now)
        reason = problem
        user += f"\n\nYour previous draft was rejected: {problem}. Write it again, following every rule."
    return SummaryDraft(available=False, reason=reason, generated_at=now)
