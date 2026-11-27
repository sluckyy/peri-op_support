"""HTTP tests for the conversational interviewer (POST .../interview/next
and .../interview/answer) against a real Postgres, with the Claude client
replaced by tests/fake_llm.py via FastAPI dependency_overrides -- no
network. The LLM-side logic itself is unit-tested in test_interview_llm.py.
"""
import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

from periop_core import db
from periop_core.enums import Speaker
from tests.fake_llm import FakeLLM, is_extraction_call

UNCLEAR = "mumble mumble"
GARBAGE = "garbage-output"


def _responder(kwargs):
    content = kwargs["messages"][0]["content"]
    if not is_extraction_call(kwargs):
        return {"utterance": "Okay, next one. " + content.rsplit("Question to ask: ", 1)[1]}
    transcript = content.rsplit("Patient's reply (transcript): ", 1)[1]
    if transcript == GARBAGE:
        return "not json"
    if transcript == UNCLEAR:
        return {"answered": False, "assertion_state": "UNKNOWN", "value": "",
                "explicit": False, "needs_clarification": True}
    return {"answered": True, "assertion_state": "AFFIRMED", "value": transcript,
            "explicit": True, "needs_clarification": False}


@pytest.fixture()
def fake_llm():
    return FakeLLM(responder=_responder)


@pytest.fixture()
def client(db_conninfo, monkeypatch, fake_llm):
    monkeypatch.setenv("PERIOP_DATABASE_URL", db_conninfo)
    import periop_api.deps as deps_module

    deps_module._DEMO_MANIFEST_ID = None
    from periop_api.app import app
    from periop_api.deps import get_llm_client

    app.dependency_overrides[get_llm_client] = lambda: fake_llm
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_llm_client, None)


def _staff_headers(client):
    username = f"staff-{uuid.uuid4().hex[:12]}"
    client.post("/api/auth/register", json={"username": username, "password": "a-fine-password"})
    token = client.post("/api/auth/login", json={"username": username, "password": "a-fine-password"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _active_session(client, activate=True):
    resp = client.post("/api/sessions", json={"subject_ref": "pt-voice", "age_years": 60, "age_source": "booking_feed"})
    session_id = resp.json()["session_id"]
    client.post(f"/api/sessions/{session_id}/notice")
    if activate:
        client.post(f"/api/sessions/{session_id}/activate")
    return session_id


def test_interview_asks_top_gap_and_records_patient_words(client, db_conninfo):
    session_id = _active_session(client)
    resp = client.post(f"/api/sessions/{session_id}/interview/next", params={"modality": "VOICE"})
    assert resp.status_code == 200, resp.text
    first = resp.json()["next"]
    assert first["concept_id"] == "CTX-001"
    assert first["question"].endswith("?")

    resp = client.post(
        f"/api/sessions/{session_id}/interview/answer",
        json={"action_id": first["action_id"], "transcript": "Jane Citizen, first of Feb 1970",
              "modality": "VOICE", "stt_confidence": 0.91},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["recorded"] is True
    assert body["next"]["concept_id"] != "CTX-001"
    # Patient-facing response: no clinical state leaks.
    for key in ("gaps", "working_facts", "conflicts", "summary"):
        assert key not in body

    summary = client.get(f"/api/sessions/{session_id}/summary", headers=_staff_headers(client)).json()
    facts = [f for f in summary["working_facts"] if f["concept"]["code"] == "CTX-001"]
    assert len(facts) == 1
    assert facts[0]["concept"]["original_text"] == "Jane Citizen, first of Feb 1970"

    with psycopg.connect(db_conninfo) as conn:
        assertion = db.list_assertions(conn, uuid.UUID(session_id))[0]
        assert assertion.provenance["entered_via"] == "LLM-001 turn extraction"
        assert assertion.source.turn_id is not None
        turns = db.list_turns(conn, uuid.UUID(session_id))
    assert [t.speaker for t in turns] == [Speaker.AGENT, Speaker.PATIENT, Speaker.AGENT]
    assert turns[1].confidence == pytest.approx(0.91)
    assert str(turns[0].action_id) == first["action_id"]


def test_unclear_answer_is_reasked_once_then_left_open_and_never_reasked(client, db_conninfo):
    session_id = _active_session(client)
    first = client.post(f"/api/sessions/{session_id}/interview/next").json()["next"]

    resp = client.post(f"/api/sessions/{session_id}/interview/answer",
                       json={"action_id": first["action_id"], "transcript": UNCLEAR}).json()
    assert resp["recorded"] is False
    assert resp["next"]["reask"] is True
    assert resp["next"]["action_id"] == first["action_id"]
    assert resp["next"]["question"].startswith("Sorry, I didn't quite catch that.")

    resp = client.post(f"/api/sessions/{session_id}/interview/answer",
                       json={"action_id": first["action_id"], "transcript": UNCLEAR}).json()
    assert resp["recorded"] is False
    second = resp["next"]
    assert second["concept_id"] != first["concept_id"]
    assert second["reask"] is False

    resp = client.post(f"/api/sessions/{session_id}/interview/answer",
                       json={"action_id": second["action_id"], "transcript": "yes"}).json()
    assert resp["next"]["concept_id"] not in (first["concept_id"], second["concept_id"])

    with psycopg.connect(db_conninfo) as conn:
        assert db.list_assertions(conn, uuid.UUID(session_id))[0].concept.code == second["concept_id"]
        assert len(db.list_assertions(conn, uuid.UUID(session_id))) == 1


def test_answering_a_stale_question_is_rejected(client):
    session_id = _active_session(client)
    first = client.post(f"/api/sessions/{session_id}/interview/next").json()["next"]
    client.post(f"/api/sessions/{session_id}/interview/answer",
                json={"action_id": first["action_id"], "transcript": "Jane Citizen"})
    resp = client.post(f"/api/sessions/{session_id}/interview/answer",
                       json={"action_id": first["action_id"], "transcript": "again"})
    assert resp.status_code == 409


def test_unknown_or_foreign_action_is_404(client):
    session_a = _active_session(client)
    session_b = _active_session(client)
    action_a = client.post(f"/api/sessions/{session_a}/interview/next").json()["next"]["action_id"]
    resp = client.post(f"/api/sessions/{session_b}/interview/answer",
                       json={"action_id": action_a, "transcript": "hello"})
    assert resp.status_code == 404
    resp = client.post(f"/api/sessions/{session_b}/interview/answer",
                       json={"action_id": str(uuid.uuid4()), "transcript": "hello"})
    assert resp.status_code == 404


def test_interview_requires_active_session(client):
    session_id = _active_session(client, activate=False)
    assert client.post(f"/api/sessions/{session_id}/interview/next").status_code == 409


def test_extraction_failure_fails_closed_without_recording(client, db_conninfo):
    session_id = _active_session(client)
    first = client.post(f"/api/sessions/{session_id}/interview/next").json()["next"]
    resp = client.post(f"/api/sessions/{session_id}/interview/answer",
                       json={"action_id": first["action_id"], "transcript": GARBAGE})
    assert resp.status_code == 503
    with psycopg.connect(db_conninfo) as conn:
        assert db.list_assertions(conn, uuid.UUID(session_id)) == []


def test_no_api_key_fails_closed_at_start(client):
    from periop_api.app import app
    from periop_api.deps import get_llm_client

    app.dependency_overrides[get_llm_client] = lambda: None
    session_id = _active_session(client)
    resp = client.post(f"/api/sessions/{session_id}/interview/next")
    assert resp.status_code == 503
    assert "form" in resp.json()["detail"]


def test_new_sessions_pin_a_manifest_naming_the_interview_models(client, db_conninfo):
    session_id = _active_session(client)
    with psycopg.connect(db_conninfo) as conn:
        session = db.get_session(conn, uuid.UUID(session_id))
        manifest = db.get_release_manifest(conn, session.manifest_id)
    assert "LLM-001" in manifest.extractor_model_id
    assert "LLM-003" in manifest.language_model_id
