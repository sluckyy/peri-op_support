"""End-to-end HTTP tests for the v1.1 Model Layer demo endpoints, against
a real Postgres instance (see conftest.py)."""
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


def _active_session(client, subject_ref="ml-patient-1"):
    resp = client.post(
        "/api/sessions",
        json={"subject_ref": subject_ref, "age_years": 60, "age_source": "booking_feed"},
    )
    session_id = resp.json()["session_id"]
    client.post(f"/api/sessions/{session_id}/notice")
    client.post(f"/api/sessions/{session_id}/activate")
    return session_id


def test_hypothesis_create_and_summary_inclusion(client):
    session_id = _active_session(client)
    resp = client.post(
        f"/api/sessions/{session_id}/hypotheses",
        json={"content": "possible pulmonary embolism", "epistemic_level": "L2_PRAGMATIC_INTERPRETATION"},
    )
    assert resp.status_code == 200, resp.text
    hyp = resp.json()
    assert hyp["status"] == "ACTIVE"

    summary = client.get(f"/api/sessions/{session_id}/summary").json()
    assert len(summary["hypotheses"]) == 1
    assert summary["hypotheses"][0]["hypothesis_id"] == hyp["hypothesis_id"]


def test_hypothesis_creation_rejects_grounded_level(client):
    session_id = _active_session(client)
    resp = client.post(
        f"/api/sessions/{session_id}/hypotheses",
        json={"content": "x", "epistemic_level": "L4_PATIENT_GROUNDED"},
    )
    assert resp.status_code == 422


def test_promotion_requires_grounding_and_succeeds_with_it(client):
    session_id = _active_session(client)
    hyp = client.post(
        f"/api/sessions/{session_id}/hypotheses",
        json={"content": "possible penicillin allergy"},
    ).json()

    # Blocked: no grounding evidence.
    resp = client.post(
        f"/api/sessions/{session_id}/hypotheses/{hyp['hypothesis_id']}/promote",
        json={"target_level": "L4_PATIENT_GROUNDED", "grounding_evidence": []},
    )
    assert resp.status_code == 409
    assert any("grounding" in r.lower() for r in resp.json()["detail"]["reasons"])

    # Succeeds with grounding evidence.
    resp = client.post(
        f"/api/sessions/{session_id}/hypotheses/{hyp['hypothesis_id']}/promote",
        json={
            "target_level": "L4_PATIENT_GROUNDED",
            "grounding_evidence": ["patient confirmed throat swelling after penicillin"],
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["hypothesis"]["status"] == "PROMOTED"
    assert body["proposition"]["epistemic_level"] == "L4_PATIENT_GROUNDED"

    summary = client.get(f"/api/sessions/{session_id}/summary").json()
    assert len(summary["propositions"]) == 1
    assert summary["hypotheses"][0]["status"] == "PROMOTED"


def test_repair_deferral_without_obligation_returns_422(client):
    session_id = _active_session(client)
    resp = client.post(
        f"/api/sessions/{session_id}/repairs",
        json={
            "repair_type": "CONTRADICTION",
            "description": "patient said two different things",
            "materiality": "MODERATE",
            "status": "DEFERRED",
            "deferred_reason": "will revisit later",
        },
    )
    assert resp.status_code == 422


def test_repair_deferral_with_inline_obligation_creation_succeeds(client):
    session_id = _active_session(client)
    resp = client.post(
        f"/api/sessions/{session_id}/repairs",
        json={
            "repair_type": "CONTRADICTION",
            "description": "patient said two different things",
            "materiality": "MODERATE",
            "status": "DEFERRED",
            "deferred_reason": "will revisit when topic recurs",
            "create_obligation": {
                "content": "revisit medication contradiction",
                "source": "repair",
                "priority": "HIGH",
                "risk": "HIGH",
            },
        },
    )
    assert resp.status_code == 200, resp.text
    repair = resp.json()
    assert repair["status"] == "DEFERRED"
    assert repair["obligation_id"] is not None

    summary = client.get(f"/api/sessions/{session_id}/summary").json()
    assert len(summary["obligations"]) == 1
    assert len(summary["repairs"]) == 1


def test_critical_open_repair_blocks_closure_via_api(client):
    session_id = _active_session(client)
    client.post(
        f"/api/sessions/{session_id}/repairs",
        json={
            "repair_type": "CONTRADICTION",
            "description": "unresolved airway account conflict",
            "materiality": "CRITICAL",
            "status": "OPEN",
        },
    )
    summary = client.get(f"/api/sessions/{session_id}/summary").json()
    assert summary["closure_preview"]["outcome"] == "BLOCKED"

    resp = client.post(f"/api/sessions/{session_id}/close")
    assert resp.status_code == 409


def test_repair_resolve_unblocks_closure(client):
    session_id = _active_session(client)
    repair = client.post(
        f"/api/sessions/{session_id}/repairs",
        json={
            "repair_type": "CONTRADICTION",
            "description": "unresolved airway account conflict",
            "materiality": "CRITICAL",
            "status": "OPEN",
        },
    ).json()

    resp = client.post(f"/api/sessions/{session_id}/repairs/{repair['repair_id']}/resolve")
    assert resp.status_code == 200
    assert resp.json()["status"] == "REPAIRED"

    resp = client.post(f"/api/sessions/{session_id}/close")
    assert resp.status_code == 200


def test_psychological_safety_signal_updates_and_persists(client):
    session_id = _active_session(client)
    resp = client.post(
        f"/api/sessions/{session_id}/psychological-safety/signal",
        json={"signal_names": ["patient_corrected_system_without_hesitation"]},
    )
    assert resp.status_code == 200, resp.text
    first = resp.json()
    assert first["estimate"] > 0.5

    summary = client.get(f"/api/sessions/{session_id}/summary").json()
    assert summary["psychological_safety"]["estimate"] == pytest.approx(first["estimate"])

    resp2 = client.post(
        f"/api/sessions/{session_id}/psychological-safety/signal",
        json={"signal_names": ["patient_showed_distress_when_correcting_system"]},
    )
    assert resp2.json()["estimate"] < first["estimate"]


def test_psychological_safety_unknown_signal_returns_422(client):
    session_id = _active_session(client)
    resp = client.post(
        f"/api/sessions/{session_id}/psychological-safety/signal",
        json={"signal_names": ["not_a_real_signal"]},
    )
    assert resp.status_code == 422


def test_humour_check_disabled_by_default(client):
    session_id = _active_session(client)
    resp = client.post(f"/api/sessions/{session_id}/humour/check", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["permitted"] is False
    assert any("off by default" in r for r in body["reasons"])


def test_humour_check_permitted_when_enabled_and_safe(client):
    session_id = _active_session(client)
    resp = client.post(
        f"/api/sessions/{session_id}/humour/check",
        json={"feature_enabled": True, "proposed_target": "self", "receptivity_known": True},
    )
    assert resp.json()["permitted"] is True


def test_causal_ecd_perfectly_discriminating_question(client):
    resp = client.post(
        "/api/tools/causal-ecd",
        json={
            "prior": {"PE": 0.5, "MI": 0.5},
            "likelihoods": {
                "yes": {"PE": 1.0, "MI": 0.0},
                "no": {"PE": 0.0, "MI": 1.0},
            },
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ecd"] == pytest.approx(1.0)
    assert body["prior_entropy"] == pytest.approx(1.0)


def test_causal_ecd_uninformative_question(client):
    resp = client.post(
        "/api/tools/causal-ecd",
        json={
            "prior": {"PE": 0.5, "MI": 0.5},
            "likelihoods": {
                "yes": {"PE": 0.5, "MI": 0.5},
                "no": {"PE": 0.5, "MI": 0.5},
            },
        },
    )
    assert resp.json()["ecd"] == pytest.approx(0.0)


def test_causal_ecd_invalid_prior_returns_422(client):
    resp = client.post(
        "/api/tools/causal-ecd",
        json={"prior": {"PE": 0.9, "MI": 0.9}, "likelihoods": {"yes": {"PE": 1.0, "MI": 1.0}}},
    )
    assert resp.status_code == 422
