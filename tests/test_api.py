"""End-to-end tests against the FastAPI app, using a real Postgres
connection (not mocked) -- see conftest.py's db_conninfo fixture. These
exercise the actual HTTP layer via FastAPI's TestClient, not just the
underlying functions, so they catch serialisation/wiring bugs the unit
tests wouldn't.
"""
import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(db_conninfo, monkeypatch):
    monkeypatch.setenv("PERIOP_DATABASE_URL", db_conninfo)
    # Force re-resolution of the demo manifest cache per test DB.
    import periop_api.deps as deps_module

    deps_module._DEMO_MANIFEST_ID = None

    from periop_api.app import app

    with TestClient(app) as c:
        yield c


def _create_eligible_session(client, subject_ref="pt-1"):
    resp = client.post(
        "/api/sessions",
        json={"subject_ref": subject_ref, "age_years": 55, "age_source": "booking_feed"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_create_session_rejects_ineligible_patient(client):
    resp = client.post(
        "/api/sessions",
        json={"subject_ref": "pt-minor", "age_years": 15, "age_source": "self_declared"},
    )
    assert resp.status_code == 422
    assert "18" in resp.json()["detail"]["reasons"][0]


def test_full_happy_path_through_conflict_to_closure(client):
    session = _create_eligible_session(client)
    session_id = session["session_id"]

    resp = client.post(f"/api/sessions/{session_id}/activate")
    assert resp.status_code == 409  # notice not acknowledged yet (INV-017)

    resp = client.post(f"/api/sessions/{session_id}/notice")
    assert resp.status_code == 200

    resp = client.post(f"/api/sessions/{session_id}/activate")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ACTIVE"

    # Agreeing assertion -> should resolve cleanly, no conflict.
    resp = client.post(
        f"/api/sessions/{session_id}/assertions",
        json={
            "concept_code": "CTX-003",
            "value": "left knee replacement",
            "assertion_state": "AFFIRMED",
            "source_type": "PATIENT",
            "speaker": "PATIENT",
        },
    )
    assert resp.status_code == 200, resp.text
    summary = resp.json()
    assert len(summary["working_facts"]) == 1
    assert len(summary["conflicts"]) == 0
    # The reconciler never produces a CONFIRMED verification_state on its
    # own (that's the documented, not-yet-implemented "fitness-based
    # tie-breaking" step -- see reconciliation.py's docstring), so a
    # single patient-only assertion correctly still surfaces as an
    # UNVERIFIED gap rather than disappearing outright. This is the
    # conservative, intended behaviour, not a bug: a single unconfirmed
    # patient report should not silently satisfy a mandatory requirement.
    ctx003_gaps = [g for g in summary["gaps"] if g["requirement_id"] == "CTX-003"]
    assert len(ctx003_gaps) == 1
    assert ctx003_gaps[0]["gap"]["gap_type"] == "UNVERIFIED"

    # Now a genuine safety-critical conflict: patient reports a penicillin
    # reaction; "EMR" (also entered via the demo shortcut) says NKDA.
    client.post(
        f"/api/sessions/{session_id}/assertions",
        json={
            "concept_code": "ALL-003",
            "value": "throat swelling after penicillin",
            "assertion_state": "AFFIRMED",
            "source_type": "PATIENT",
            "speaker": "PATIENT",
        },
    )
    resp = client.post(
        f"/api/sessions/{session_id}/assertions",
        json={
            "concept_code": "ALL-003",
            "value": "NKDA",
            "assertion_state": "NEGATED",
            "source_type": "EMR",
            "speaker": "SYSTEM",
        },
    )
    summary = resp.json()
    assert len(summary["conflicts"]) == 1
    assert summary["conflicts"][0]["materiality"] == "CRITICAL"
    assert summary["closure_preview"]["outcome"] == "COMPLETE_WITH_OPEN_ACTIONS"

    # A critical conflict downgrades closure but does not block it (only
    # an unowned critical Task does, per INV-010) -- confirm close succeeds.
    resp = client.post(f"/api/sessions/{session_id}/close")
    assert resp.status_code == 200, resp.text
    assert resp.json()["session"]["status"] == "COMPLETE"


def test_concepts_endpoint_returns_all_343(client):
    resp = client.get("/api/concepts")
    assert resp.status_code == 200
    assert len(resp.json()) == 343


def test_backdated_assertion_surfaces_as_a_stale_gap(client):
    """Reconciliation's freshness assessment (step 3), exercised through
    the real HTTP layer: a single-source assertion backdated well past
    the default staleness threshold should show up as a STALE gap, not
    silently satisfy the requirement forever."""
    session = _create_eligible_session(client, subject_ref="pt-stale")
    session_id = session["session_id"]
    client.post(f"/api/sessions/{session_id}/notice")
    client.post(f"/api/sessions/{session_id}/activate")

    old_time = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat()
    resp = client.post(
        f"/api/sessions/{session_id}/assertions",
        json={
            "concept_code": "CUR-002",
            "value": "no recent change",
            "assertion_state": "AFFIRMED",
            "source_type": "PATIENT",
            "speaker": "PATIENT",
            "assertion_time": old_time,
        },
    )
    assert resp.status_code == 200, resp.text
    summary = resp.json()

    cur002_gaps = [g for g in summary["gaps"] if g["requirement_id"] == "CUR-002"]
    assert len(cur002_gaps) == 1
    assert cur002_gaps[0]["gap"]["gap_type"] == "STALE"

    fact = next(f for f in summary["working_facts"] if f["concept"]["code"] == "CUR-002")
    assert fact["verification_state"] == "STALE"
