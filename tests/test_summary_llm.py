"""Tests for LLM-005 summary drafting (periop_core.summary_llm): the
deterministic validator, retry/fallback behaviour, and the endpoint.
No network -- tests/fake_llm.py stands in for Claude."""
import uuid
from datetime import datetime, timezone

import pytest

from periop_core.clinical_summary import AttentionItem, ClinicalSummary, SummaryCounts
from periop_core.summary_llm import DRAFT_LABEL, draft_summary, validate_narrative
from tests.fake_llm import FakeLLM

GOOD = ("Flagged: conflicting answers about the reaction phenotype; the patient reports throat swelling "
        "after penicillin while the EMR records NKDA, and closure is blocked pending review. "
        "Patient reports penicillin allergy. Mandatory questions remain unanswered.")


def _summary(attention=None):
    attention = attention if attention is not None else [
        AttentionItem(kind="closure_block", severity="CRITICAL", title="Closure is blocked", detail="x"),
        AttentionItem(kind="conflict", severity="CRITICAL", title="Conflicting answers: Reaction phenotype",
                      detail="y", concept_id="ALL-003", concept="Reaction phenotype"),
    ]
    return ClinicalSummary(
        session_id=uuid.uuid4(), subject_ref="pt", session_status="ACTIVE",
        generated_at=datetime.now(timezone.utc), closure_outcome="BLOCKED", attention=attention,
        safety_findings=[], domains=[], unanswered_mandatory=[], not_applicable=[],
        counts=SummaryCounts(answered=0, positives=0, negatives=0, unsure=0, conflicting=0,
                             unanswered=0, unanswered_mandatory=0, not_applicable=0),
    )


def test_validator_accepts_a_draft_that_names_every_flagged_item():
    assert validate_narrative(GOOD, _summary()) is None


@pytest.mark.parametrize("text, reason", [
    ("", "empty"),
    ("x" * 3000, "too long"),
    (GOOD + " The patient is fit for surgery.", "prohibited"),
    (GOOD + " This has been reviewed by the anaesthetist.", "prohibited"),
    (GOOD + " I recommend an allergy referral.", "prohibited"),
    (GOOD + " Likely diagnosis: true allergy.", "prohibited"),
    ("Patient reports penicillin allergy. Closure is blocked.", "omitted flagged item"),
])
def test_validator_rejects(text, reason):
    assert reason in validate_narrative(text, _summary())


def test_draft_returns_validated_narrative_with_label_and_model():
    llm = FakeLLM([{"narrative": GOOD}])
    draft = draft_summary(llm, _summary())
    assert draft.available is True
    assert draft.narrative == GOOD
    assert draft.label == DRAFT_LABEL
    assert draft.model == "claude-opus-5-5"
    prompt = llm.calls[0]["messages"][0]["content"]
    assert "Reaction phenotype" in prompt and "must mention" in prompt


def test_draft_regenerates_once_then_succeeds():
    llm = FakeLLM([{"narrative": "Patient reports allergy."}, {"narrative": GOOD}])
    draft = draft_summary(llm, _summary())
    assert draft.available is True
    assert len(llm.calls) == 2
    assert "previous draft was rejected" in llm.calls[1]["messages"][0]["content"]


def test_draft_falls_back_after_two_rejections():
    llm = FakeLLM([{"narrative": GOOD + " Fit for surgery."}, {"narrative": GOOD + " Fit for surgery."}])
    draft = draft_summary(llm, _summary())
    assert draft.available is False
    assert draft.narrative is None
    assert "prohibited" in draft.reason


def test_draft_without_client_is_unavailable_not_an_error():
    draft = draft_summary(None, _summary())
    assert draft.available is False
    assert "not configured" in draft.reason


def test_draft_endpoint_requires_auth_and_uses_governed_state(db_conninfo, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("PERIOP_DATABASE_URL", db_conninfo)
    import periop_api.deps as deps_module

    deps_module._DEMO_MANIFEST_ID = None
    from periop_api.app import app
    from periop_api.deps import get_llm_client

    llm = FakeLLM(responder=lambda kw: {"narrative": "Patient reports a penicillin allergy. No flagged items."})
    app.dependency_overrides[get_llm_client] = lambda: llm
    try:
        with TestClient(app) as c:
            username = f"staff-{uuid.uuid4().hex[:12]}"
            c.post("/api/auth/register", json={"username": username, "password": "a-fine-password"})
            token = c.post("/api/auth/login", json={"username": username, "password": "a-fine-password"}).json()["token"]
            sid = c.post("/api/sessions", json={"subject_ref": "pt-draft", "age_years": 50,
                                                "age_source": "booking_feed"}).json()["session_id"]
            c.post(f"/api/sessions/{sid}/notice")
            c.post(f"/api/sessions/{sid}/activate")
            c.post(f"/api/sessions/{sid}/assertions", json={
                "concept_code": "ALL-001", "assertion_state": "AFFIRMED", "value": "penicillin",
                "source_type": "PATIENT"})

            assert c.post(f"/api/sessions/{sid}/clinical-summary/draft").status_code == 401
            resp = c.post(f"/api/sessions/{sid}/clinical-summary/draft",
                          headers={"Authorization": f"Bearer {token}"})
    finally:
        app.dependency_overrides.pop(get_llm_client, None)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["available"] is True
    assert body["label"] == DRAFT_LABEL
    assert "penicillin" in llm.calls[0]["messages"][0]["content"]
