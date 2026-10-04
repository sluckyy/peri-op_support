"""End-to-end tests against the FastAPI app, using a real Postgres
connection (not mocked) -- see conftest.py's db_conninfo fixture. These
exercise the actual HTTP layer via FastAPI's TestClient, not just the
underlying functions, so they catch serialisation/wiring bugs the unit
tests wouldn't.
"""
import os
import uuid
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
    # A plain Conflict on its own only downgrades closure, but ALL-003 is
    # one of the identity/procedure/allergy/anaesthetic/medication
    # prefixes (periop_core.reconciliation.CRITICAL_CONCEPT_PREFIXES), so
    # the ConflictReview it auto-logged now blocks closure outright until
    # a clinician actually resolves it -- logging a safety-critical
    # disagreement isn't enough on its own if nobody acts on it.
    assert summary["closure_preview"]["outcome"] == "BLOCKED"
    review_id = summary["conflict_reviews"][0]["review_id"]

    resp = client.post(f"/api/sessions/{session_id}/close")
    assert resp.status_code == 409, resp.text
    assert "conflict review" in resp.json()["detail"]["blocking_reasons"][0].lower()

    resp = client.post(
        f"/api/sessions/{session_id}/conflict-reviews/{review_id}/resolve",
        json={
            "status": "RECONCILED",
            "resolved_by": "dr-smith",
            "rationale": "EMR note is contemporaneous; patient recall is unreliable here",
            "resolved_value": "throat swelling after penicillin",
        },
    )
    assert resp.status_code == 200, resp.text

    # Resolving the review unblocks closure, but the underlying Conflict
    # itself is still OPEN (nothing here auto-resolves step 7) -- so it
    # still downgrades to COMPLETE_WITH_OPEN_ACTIONS rather than COMPLETE.
    resp = client.post(f"/api/sessions/{session_id}/close")
    assert resp.status_code == 200, resp.text
    assert resp.json()["session"]["status"] == "COMPLETE"


def test_conflicting_assertions_log_a_durable_conflict_review(client):
    """A ConflictReview is logged automatically the moment reconciliation
    detects a real disagreement, carrying each side verbatim (source,
    speaker, value, the patient's own words, and when it was said) --
    not just the abstract Conflict row, which gets recomputed (and would
    lose any clinician decision) on every subsequent summary fetch."""
    session = _create_eligible_session(client, subject_ref="pt-conflict-review")
    session_id = session["session_id"]
    client.post(f"/api/sessions/{session_id}/notice")
    client.post(f"/api/sessions/{session_id}/activate")

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
    assert len(summary["conflict_reviews"]) == 1
    review = summary["conflict_reviews"][0]
    assert review["status"] == "OPEN"
    assert len(review["sides"]) == 2
    source_types = {s["source_type"] for s in review["sides"]}
    assert source_types == {"PATIENT", "EMR"}
    values = {s["value"] for s in review["sides"]}
    assert values == {"throat swelling after penicillin", "NKDA"}

    # Fetching the summary again (no new assertion) must NOT create a
    # second review for the same disagreement.
    resp = client.get(f"/api/sessions/{session_id}/summary")
    assert len(resp.json()["conflict_reviews"]) == 1


def test_resolving_a_conflict_review_persists_across_recompute(client):
    session = _create_eligible_session(client, subject_ref="pt-conflict-resolve")
    session_id = session["session_id"]
    client.post(f"/api/sessions/{session_id}/notice")
    client.post(f"/api/sessions/{session_id}/activate")
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
    review_id = resp.json()["conflict_reviews"][0]["review_id"]

    # RECONCILED without resolved_value is rejected -- nothing was
    # actually decided.
    resp = client.post(
        f"/api/sessions/{session_id}/conflict-reviews/{review_id}/resolve",
        json={"status": "RECONCILED", "resolved_by": "dr-smith", "rationale": "..."},
    )
    assert resp.status_code == 422

    resp = client.post(
        f"/api/sessions/{session_id}/conflict-reviews/{review_id}/resolve",
        json={
            "status": "RECONCILED",
            "resolved_by": "dr-smith",
            "rationale": "EMR note is contemporaneous; patient recall is unreliable here",
            "resolved_value": "throat swelling after penicillin",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "RECONCILED"
    assert resp.json()["resolution"]["resolved_by"] == "dr-smith"

    # Resolving an already-resolved review is rejected.
    resp = client.post(
        f"/api/sessions/{session_id}/conflict-reviews/{review_id}/resolve",
        json={
            "status": "ESCALATED",
            "resolved_by": "dr-jones",
            "rationale": "second opinion",
        },
    )
    assert resp.status_code == 409

    # Recomputing the summary (e.g. a fresh GET) must not wipe the
    # resolution -- this is exactly the bug ConflictReview exists to avoid.
    resp = client.get(f"/api/sessions/{session_id}/summary")
    review = resp.json()["conflict_reviews"][0]
    assert review["status"] == "RECONCILED"
    assert review["resolution"]["resolved_value"] == "throat swelling after penicillin"


def test_resolving_an_unknown_conflict_review_404s(client):
    session = _create_eligible_session(client, subject_ref="pt-conflict-404")
    session_id = session["session_id"]
    resp = client.post(
        f"/api/sessions/{session_id}/conflict-reviews/{uuid.uuid4()}/resolve",
        json={"status": "ESCALATED", "resolved_by": "dr-smith", "rationale": "..."},
    )
    assert resp.status_code == 404


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


def test_audit_lineage_reconstructs_session_lifecycle(client):
    """SVC-014 / NFR-012 ('Audit reconstruction test passes'): the audit
    trail should let you reconstruct exactly what happened to a session,
    in order, without re-deriving it from the other tables."""
    session = _create_eligible_session(client, subject_ref="pt-audit")
    session_id = session["session_id"]

    client.post(f"/api/sessions/{session_id}/notice")
    client.post(f"/api/sessions/{session_id}/activate")
    client.post(
        f"/api/sessions/{session_id}/assertions",
        json={
            "concept_code": "CTX-003",
            "value": "left knee replacement",
            "assertion_state": "AFFIRMED",
            "source_type": "PATIENT",
            "speaker": "PATIENT",
        },
    )
    client.post(f"/api/sessions/{session_id}/close")

    resp = client.get(f"/api/sessions/{session_id}/audit")
    assert resp.status_code == 200, resp.text
    events = resp.json()
    assert [e["event_type"] for e in events] == [
        "SESSION_CREATED",
        "NOTICE_ACKNOWLEDGED",
        "SESSION_ACTIVATED",
        "ASSERTION_ADDED",
        "SESSION_CLOSED",
    ]
    # Oldest first, and the record of what was created is enough to
    # reconstruct it without going back to the assertion table.
    assert events[0]["payload"]["subject_ref"] == "pt-audit"
    assert events[3]["payload"]["concept_code"] == "CTX-003"
    assert events[3]["entity_id"] is not None  # points at the actual Assertion row


def test_audit_lineage_includes_model_layer_mutations(client):
    """The audit trail isn't just for the Phase 1 core lifecycle -- every
    v1.1 Model Layer mutation (hypotheses, propositions, obligations,
    contradictions, uncertainties, repairs, psychological-safety signals)
    must append its own event too."""
    session = _create_eligible_session(client, subject_ref="pt-audit-ml")
    session_id = session["session_id"]
    client.post(f"/api/sessions/{session_id}/notice")
    client.post(f"/api/sessions/{session_id}/activate")

    hyp = client.post(
        f"/api/sessions/{session_id}/hypotheses",
        json={"content": "possible penicillin allergy"},
    ).json()
    promotion = client.post(
        f"/api/sessions/{session_id}/hypotheses/{hyp['hypothesis_id']}/promote",
        json={
            "target_level": "L4_PATIENT_GROUNDED",
            "grounding_evidence": ["patient confirmed throat swelling after penicillin"],
        },
    ).json()
    client.post(
        f"/api/sessions/{session_id}/propositions/{promotion['proposition']['proposition_id']}/correct",
        json={"content": "no penicillin allergy after all", "grounding_evidence": ["patient clarified on follow-up"]},
    )
    client.post(
        f"/api/sessions/{session_id}/obligations",
        json={"content": "confirm allergy status with pharmacy", "source": "repair"},
    )
    client.post(
        f"/api/sessions/{session_id}/contradictions",
        json={
            "description": "patient gave two different allergy histories",
            "involved_ids": [str(uuid.uuid4()), str(uuid.uuid4())],
        },
    )
    client.post(
        f"/api/sessions/{session_id}/uncertainties",
        json={"description": "unclear which knee was operated on"},
    )
    repair = client.post(
        f"/api/sessions/{session_id}/repairs",
        json={
            "repair_type": "FACTUAL_ACCURACY",
            "description": "corrected allergy status",
            "materiality": "HIGH",
        },
    ).json()
    client.post(f"/api/sessions/{session_id}/repairs/{repair['repair_id']}/resolve")
    client.post(
        f"/api/sessions/{session_id}/psychological-safety/signal",
        json={"signal_names": ["patient_asked_a_question"]},
    )

    resp = client.get(f"/api/sessions/{session_id}/audit")
    assert resp.status_code == 200, resp.text
    event_types = [e["event_type"] for e in resp.json()]
    assert event_types == [
        "SESSION_CREATED",
        "NOTICE_ACKNOWLEDGED",
        "SESSION_ACTIVATED",
        "HYPOTHESIS_CREATED",
        "HYPOTHESIS_PROMOTED",
        "PROPOSITION_CORRECTED",
        "OBLIGATION_CREATED",
        "CONTRADICTION_LOGGED",
        "UNCERTAINTY_LOGGED",
        "REPAIR_CREATED",
        "REPAIR_RESOLVED",
        "PSYCHOLOGICAL_SAFETY_SIGNAL_APPLIED",
    ]


def test_audit_lineage_404s_for_unknown_session(client):
    resp = client.get(f"/api/sessions/{uuid.uuid4()}/audit")
    assert resp.status_code == 404
