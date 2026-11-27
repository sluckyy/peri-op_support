"""Tests for the red-flag escalation map (periop_core.escalation) and its
wiring: tasks raised from either answer path, the fixed patient safety
message, closure blocking, and the acknowledge/resolve lifecycle."""
import dataclasses
import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

from periop_core import escalation
from periop_core.dataset import default_concept_labels, default_requirements
from periop_core.enums import AssertionState
from periop_core.escalation import EscalationRule, load_escalation_rules, validate_rules
from tests.fake_llm import FakeLLM, is_extraction_call

ALL = frozenset({AssertionState.AFFIRMED})


def _approved(rules):
    return tuple(dataclasses.replace(r, status="APPROVED", approved_by="Dr Test") for r in rules)


# ------------------------------------------------------------ the file

def test_shipped_map_loads_and_every_urgent_rule_has_a_message():
    rules = load_escalation_rules()
    assert len(rules) >= 15
    for r in rules:
        assert r.rationale
        assert bool(r.patient_message) == (r.tier == "URGENT")


def test_shipped_map_only_uses_answers_a_yes_no_can_judge():
    labels = default_concept_labels()
    for r in load_escalation_rules():
        for c in r.concepts:
            assert labels[c]["response_type"] == "boolean" or c == "PSY-018", (r.rule_id, c)


# ------------------------------------------------------------ validation

def _rule(**kw):
    base = dict(rule_id="X", concepts=("CARD-005",), trigger_states=ALL, escalation_class="ESC-001",
                tier="RED", patient_message="", rationale="r", status="PROPOSED")
    base.update(kw)
    return EscalationRule(**base)


@pytest.mark.parametrize("rule, message", [
    (_rule(tier="URGENT"), "need an approved patient safety message"),
    (_rule(tier="AMBER", patient_message="call 000"), "only URGENT rules"),
    (_rule(escalation_class="ESC-099"), "unknown escalation class"),
    (_rule(status="APPROVED"), "name who approved"),
    (_rule(concepts=("NOPE-1",)), "unknown concept"),
    (_rule(tier="ORANGE"), "unknown tier"),
])
def test_validator_rejects_bad_rules(rule, message):
    with pytest.raises(ValueError, match=message):
        validate_rules([rule], default_requirements())


def test_validator_rejects_one_answer_mapping_to_two_tiers():
    with pytest.raises(ValueError, match="already covered"):
        validate_rules([_rule(rule_id="A"), _rule(rule_id="B", tier="AMBER")], default_requirements())


def test_evaluate_triggers_only_on_listed_states():
    from periop_core.enums import Certainty, Speaker
    from periop_core.models import Assertion, ConceptReference, SourceReference

    def a(state):
        return Assertion(session_id=uuid.uuid4(), subject_ref="p", concept=ConceptReference(original_text="x", code="CARD-005"),
                         assertion_state=state, source=SourceReference(source_type="PATIENT", speaker=Speaker.PATIENT),
                         certainty=Certainty.EXPLICIT, provenance={"n": 1})
    rule = _rule()
    assert escalation.evaluate([rule], [a(AssertionState.NEGATED)]) == []
    hit = escalation.evaluate([rule], [a(AssertionState.NEGATED), a(AssertionState.AFFIRMED)])
    assert len(hit) == 1 and len(hit[0].assertion_ids) == 1


# ------------------------------------------------------------ via the API

@pytest.fixture()
def client(db_conninfo, monkeypatch):
    monkeypatch.setenv("PERIOP_DATABASE_URL", db_conninfo)
    monkeypatch.setattr(escalation, "approved_escalation_rules", lambda: _approved(load_escalation_rules()))
    import periop_api.deps as deps_module

    deps_module._DEMO_MANIFEST_ID = None
    from periop_api.app import app

    with TestClient(app) as c:
        username = f"staff-{uuid.uuid4().hex[:12]}"
        c.post("/api/auth/register", json={"username": username, "password": "a-fine-password"})
        c.staff = {"Authorization": "Bearer " + c.post("/api/auth/login", json={
            "username": username, "password": "a-fine-password"}).json()["token"]}
        c.staff_username = username
        yield c


def _session(c):
    sid = c.post("/api/sessions", json={"subject_ref": "pt-esc", "age_years": 58, "age_source": "booking_feed"}).json()["session_id"]
    c.post(f"/api/sessions/{sid}/notice")
    c.post(f"/api/sessions/{sid}/activate")
    return sid


def _say(c, sid, code, state):
    resp = c.post(f"/api/sessions/{sid}/assertions", json={
        "concept_code": code, "assertion_state": state, "source_type": "PATIENT"})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _tasks(c, sid):
    return c.get(f"/api/sessions/{sid}/summary", headers=c.staff).json()["tasks"]


def test_urgent_answer_shows_the_approved_message_once_and_blocks_closure(client, db_conninfo):
    sid = _session(client)
    body = _say(client, sid, "CARD-005", "AFFIRMED")
    expected = next(r.patient_message for r in load_escalation_rules() if "CARD-005" in r.concepts)
    assert body["safety_message"] == expected
    assert "000" in body["safety_message"]

    tasks = _tasks(client, sid)
    assert len(tasks) == 1
    task = tasks[0]
    assert (task["type"], task["priority"], task["owner_ref"]) == ("SAFETY", "CRITICAL", None)
    assert task["reason"]["rule_id"] == "ESC-R01"
    summary = client.get(f"/api/sessions/{sid}/summary", headers=client.staff).json()
    assert summary["closure_preview"]["outcome"] == "BLOCKED"

    again = _say(client, sid, "CARD-005", "AFFIRMED")
    assert again["safety_message"] is None
    assert len(_tasks(client, sid)) == 1

    audit = client.get(f"/api/sessions/{sid}/audit", headers=client.staff).json()
    raised = [e for e in audit if e["event_type"] == "ESCALATION_RAISED"]
    assert len(raised) == 1
    assert raised[0]["payload"]["patient_message_shown"] == expected


def test_amber_goes_to_review_flags_and_red_to_attention(client):
    sid = _session(client)
    assert _say(client, sid, "ENDO-001", "AFFIRMED")["safety_message"] is None
    _say(client, sid, "FAM-002", "UNCERTAIN")
    s = client.get(f"/api/sessions/{sid}/clinical-summary", headers=client.staff).json()
    flags = {f["concept_id"]: f for f in s["review_flags"]}
    assert flags["ENDO-001"]["severity"] == "MODERATE"
    assert flags["ENDO-001"]["title"] == "Review: Diabetes"
    red = next(a for a in s["attention"] if a["kind"] == "task")
    assert red["concept_id"] == "FAM-002"
    assert red["title"] == "Red flag: Malignant hyperthermia"
    assert red["severity"] == "HIGH"
    assert "Unowned" in red["detail"]
    assert "ENDO-001" not in {a.get("concept_id") for a in s["attention"]}


def test_unowned_urgent_task_is_listed_once_and_says_it_blocks_closure(client):
    sid = _session(client)
    _say(client, sid, "CARD-005", "AFFIRMED")
    s = client.get(f"/api/sessions/{sid}/clinical-summary", headers=client.staff).json()
    assert s["closure_outcome"] == "BLOCKED"
    assert not [a for a in s["attention"] if a["kind"] == "closure_block"]
    urgent = [a for a in s["attention"] if a["kind"] == "task"]
    assert len(urgent) == 1
    assert urgent[0]["title"] == "URGENT: Current chest pain"
    assert "blocks closure" in urgent[0]["detail"]


def test_a_clear_no_raises_nothing(client):
    sid = _session(client)
    for code in ("CARD-005", "FAM-002", "ENDO-001"):
        assert _say(client, sid, code, "NEGATED")["safety_message"] is None
    assert _tasks(client, sid) == []


def test_acknowledge_then_resolve_lifecycle(client):
    sid = _session(client)
    _say(client, sid, "CARD-005", "AFFIRMED")
    task_id = _tasks(client, sid)[0]["task_id"]
    base = f"/api/sessions/{sid}/tasks/{task_id}"

    assert client.post(f"{base}/acknowledge").status_code == 401
    ack = client.post(f"{base}/acknowledge", headers=client.staff)
    assert ack.status_code == 200, ack.text
    assert (ack.json()["owner_ref"], ack.json()["status"]) == (client.staff_username, "ACKNOWLEDGED")
    summary = client.get(f"/api/sessions/{sid}/summary", headers=client.staff).json()
    assert summary["closure_preview"]["outcome"] == "COMPLETE_WITH_OPEN_ACTIONS"

    assert client.post(f"{base}/resolve", headers=client.staff, json={"note": ""}).status_code == 422
    res = client.post(f"{base}/resolve", headers=client.staff, json={"note": "Exertional only; seen in clinic"})
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "RESOLVED"
    assert res.json()["reason"]["resolution"]["by"] == client.staff_username
    assert client.post(f"{base}/acknowledge", headers=client.staff).status_code == 409

    s = client.get(f"/api/sessions/{sid}/clinical-summary", headers=client.staff).json()
    assert not [a for a in s["attention"] if a["kind"] == "task"]
    events = [e["event_type"] for e in client.get(f"/api/sessions/{sid}/audit", headers=client.staff).json()]
    assert {"ESCALATION_RAISED", "TASK_ACKNOWLEDGED", "TASK_RESOLVED"} <= set(events)


def test_task_from_another_session_is_404(client):
    a, b = _session(client), _session(client)
    _say(client, a, "CARD-005", "AFFIRMED")
    task_id = _tasks(client, a)[0]["task_id"]
    assert client.post(f"/api/sessions/{b}/tasks/{task_id}/acknowledge", headers=client.staff).status_code == 404


def test_interview_urgent_answer_records_the_interrupt_and_keeps_the_next_question_answerable(
    db_conninfo, monkeypatch
):
    urgent = EscalationRule("T-U", ("CTX-001",), frozenset({AssertionState.AFFIRMED}), "ESC-001", "URGENT",
                            "Test safety message: call 000.", "test", "APPROVED", "Dr Test")
    monkeypatch.setenv("PERIOP_DATABASE_URL", db_conninfo)
    monkeypatch.setattr(escalation, "approved_escalation_rules", lambda: (urgent,))
    import periop_api.deps as deps_module

    deps_module._DEMO_MANIFEST_ID = None
    from periop_api.app import app
    from periop_api.deps import get_llm_client

    def responder(kw):
        if not is_extraction_call(kw):
            return {"utterance": kw["messages"][0]["content"].rsplit("Question to ask: ", 1)[1]}
        return {"answered": True, "assertion_state": "AFFIRMED", "value": "yes", "explicit": True,
                "needs_clarification": False}

    app.dependency_overrides[get_llm_client] = lambda: FakeLLM(responder=responder)
    try:
        with TestClient(app) as c:
            sid = _session(c)
            first = c.post(f"/api/sessions/{sid}/interview/next").json()["next"]
            assert first["concept_id"] == "CTX-001"
            body = c.post(f"/api/sessions/{sid}/interview/answer",
                          json={"action_id": first["action_id"], "transcript": "Jane Citizen"}).json()
            assert body["safety_message"] == "Test safety message: call 000."
            nxt = body["next"]
            resp = c.post(f"/api/sessions/{sid}/interview/answer",
                          json={"action_id": nxt["action_id"], "transcript": "a knee replacement"})
            assert resp.status_code == 200, resp.text
    finally:
        app.dependency_overrides.pop(get_llm_client, None)

    from periop_core import db
    with psycopg.connect(db_conninfo) as conn:
        turns = db.list_turns(conn, uuid.UUID(sid))
    agent_texts = [t.content for t in turns if t.speaker.value == "AGENT"]
    assert "Test safety message: call 000." in agent_texts
    assert agent_texts.index("Test safety message: call 000.") == 1  # after Q1, before Q2
