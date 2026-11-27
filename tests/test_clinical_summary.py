"""Tests for the clinician-facing structured summary
(periop_core.clinical_summary, GET .../clinical-summary), driven through
the real API against Postgres."""
import uuid

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(db_conninfo, monkeypatch):
    monkeypatch.setenv("PERIOP_DATABASE_URL", db_conninfo)
    import periop_api.deps as deps_module

    deps_module._DEMO_MANIFEST_ID = None
    from periop_api.app import app

    with TestClient(app) as c:
        yield c


def _staff(client):
    username = f"staff-{uuid.uuid4().hex[:12]}"
    client.post("/api/auth/register", json={"username": username, "password": "a-fine-password"})
    token = client.post("/api/auth/login", json={"username": username, "password": "a-fine-password"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _session(client):
    sid = client.post("/api/sessions", json={"subject_ref": "pt-summary", "age_years": 61,
                                             "age_source": "booking_feed"}).json()["session_id"]
    client.post(f"/api/sessions/{sid}/notice")
    client.post(f"/api/sessions/{sid}/activate")
    return sid


def _say(client, sid, code, state, value=None, words=None, source="PATIENT", speaker="PATIENT"):
    body = {"concept_code": code, "assertion_state": state, "value": value,
            "source_type": source, "speaker": speaker}
    if words:
        body["concept_text"] = words
    resp = client.post(f"/api/sessions/{sid}/assertions", json=body)
    assert resp.status_code == 200, resp.text


def test_clinical_summary_requires_auth(client):
    sid = _session(client)
    assert client.get(f"/api/sessions/{sid}/clinical-summary").status_code == 401


def test_clinical_summary_puts_critical_issues_first_and_keeps_sources(client):
    sid = _session(client)
    _say(client, sid, "ALL-001", "AFFIRMED", "penicillin", words="yes I'm allergic to penicillin")
    _say(client, sid, "CARD-001", "NEGATED", words="no, my blood pressure is fine")
    _say(client, sid, "AIR-001", "UNCERTAIN", words="not sure, maybe a bit")
    _say(client, sid, "ALL-003", "AFFIRMED", "throat swelling", words="my throat swelled up")
    _say(client, sid, "ALL-003", "NEGATED", "NKDA", source="EMR", speaker="SYSTEM")

    resp = client.get(f"/api/sessions/{sid}/clinical-summary", headers=_staff(client))
    assert resp.status_code == 200, resp.text
    s = resp.json()

    # SB-019: never implies clinician review.
    assert s["review_status"] == "NOT_CLINICIAN_REVIEWED"

    # Critical issues first: the blocked closure and the allergy conflict, then the unsure airway answer.
    kinds = [(a["kind"], a["severity"]) for a in s["attention"]]
    assert kinds[0][1] == "CRITICAL"
    assert ("conflict", "CRITICAL") in kinds
    assert ("closure_block", "CRITICAL") in kinds
    assert ("unsure_safety_answer", "HIGH") in kinds
    severities = [a["severity"] for a in s["attention"]]
    assert severities == sorted(severities, key=["CRITICAL", "HIGH", "MODERATE", "LOW"].index)

    conflict = next(a for a in s["attention"] if a["kind"] == "conflict")
    assert conflict["concept_id"] == "ALL-003"
    said = {src["source_type"]: src for src in conflict["sources"]}
    assert said["PATIENT"]["said"] == "my throat swelled up"
    assert said["EMR"]["value"] == "NKDA"
    assert "Awaiting clinician review" in conflict["detail"]

    # Safety-critical positives surface at the top too.
    safety = {f["concept_id"]: f for f in s["safety_findings"]}
    assert safety["ALL-001"]["answer"] == "penicillin"
    assert safety["ALL-001"]["sources"][0]["said"] == "yes I'm allergic to penicillin"
    assert safety["ALL-001"]["verification"] == "patient-reported, unverified"

    # Findings grouped by body system, in dataset order.
    domains = [d["domain"] for d in s["domains"]]
    assert domains.index("Cardiovascular") < domains.index("Airway, dental and anatomical history")
    cardio = next(d for d in s["domains"] if d["domain"] == "Cardiovascular")
    assert [f["concept_id"] for f in cardio["negatives"]] == ["CARD-001"]
    airway = next(d for d in s["domains"] if d["domain"] == "Airway, dental and anatomical history")
    assert airway["unsure"][0]["answer"] == "Unsure"
    allergy = next(d for d in s["domains"] if d["domain"].startswith("Allergy"))
    assert [f["concept_id"] for f in allergy["conflicting"]] == ["ALL-003"]

    # Outstanding mandatory questions are listed, and the counts add up.
    unanswered = {u["concept_id"] for u in s["unanswered_mandatory"]}
    assert "CTX-001" in unanswered
    assert "ALL-001" not in unanswered
    c = s["counts"]
    assert (c["positives"], c["negatives"], c["unsure"], c["conflicting"]) == (1, 1, 1, 1)
    assert c["answered"] == 4
    assert c["unanswered_mandatory"] == len(s["unanswered_mandatory"])


def test_resolved_conflict_review_is_described_not_hidden(client):
    sid = _session(client)
    headers = _staff(client)
    _say(client, sid, "ALL-003", "AFFIRMED", "throat swelling", words="my throat swelled up")
    _say(client, sid, "ALL-003", "NEGATED", "NKDA", source="EMR", speaker="SYSTEM")
    review_id = client.get(f"/api/sessions/{sid}/summary", headers=headers).json()["conflict_reviews"][0]["review_id"]
    client.post(f"/api/sessions/{sid}/conflict-reviews/{review_id}/resolve", headers=headers, json={
        "status": "RECONCILED", "rationale": "patient account is specific", "resolved_value": "throat swelling"})

    s = client.get(f"/api/sessions/{sid}/clinical-summary", headers=headers).json()
    conflict = next(a for a in s["attention"] if a["kind"] == "conflict")
    assert "Reconciled by" in conflict["detail"]
    assert "patient account is specific" in conflict["detail"]


def test_skipped_follow_ups_are_listed_with_the_reason(client):
    sid = _session(client)
    _say(client, sid, "NEURO-004", "NEGATED", words="no seizures")
    s = client.get(f"/api/sessions/{sid}/clinical-summary", headers=_staff(client)).json()
    skipped = {n["concept_id"]: n for n in s["not_applicable"]}
    assert skipped["NEURO-005"]["because"] == ["Epilepsy/seizures: No"]
    assert s["counts"]["not_applicable"] == len(s["not_applicable"])


def test_concurrent_recomputes_for_one_session_are_serialised(client, db_conninfo):
    """The recompute deletes and re-inserts derived rows; two at once used
    to fail with FK violations (the staff page fires several summary
    requests together). A second recompute must wait for the first."""
    import psycopg

    from periop_api.app import _recompute_and_summarise

    sid = uuid.UUID(_session(client))
    _say(client, str(sid), "ALL-001", "NEGATED", words="no allergies")

    with psycopg.connect(db_conninfo) as first, psycopg.connect(db_conninfo) as second:
        _recompute_and_summarise(first, sid)  # holds the session lock until `first` commits
        second.execute("SET lock_timeout = '300ms'")
        with pytest.raises(psycopg.errors.LockNotAvailable):
            _recompute_and_summarise(second, sid)
        second.rollback()
        first.commit()
        _recompute_and_summarise(second, sid)  # free once the first transaction ends
        second.commit()
