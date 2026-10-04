"""Unit tests for periop_core.auth's cryptographic primitives, plus
end-to-end HTTP tests for the auth boundary itself: which endpoints
are patient-facing/unauthenticated versus staff-only/require_auth-gated
-- see README and periop_api.app for the full classification.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from periop_core.auth import hash_password, new_session, verify_password


# --------------------------------------------------------- unit tests

def test_hash_password_round_trip():
    stored = hash_password("correct-horse-battery")
    assert verify_password("correct-horse-battery", stored) is True


def test_hash_password_rejects_wrong_password():
    stored = hash_password("correct-horse-battery")
    assert verify_password("wrong-password-entirely", stored) is False


def test_hash_password_rejects_too_short():
    with pytest.raises(ValueError):
        hash_password("short")


def test_hash_password_salts_differ_across_calls():
    # Same password, two calls -> different stored hashes (different
    # random salt each time), so a precomputed rainbow table over the
    # raw hash can't be reused across users.
    a = hash_password("correct-horse-battery")
    b = hash_password("correct-horse-battery")
    assert a != b
    assert verify_password("correct-horse-battery", a) is True
    assert verify_password("correct-horse-battery", b) is True


def test_verify_password_rejects_malformed_stored_hash():
    assert verify_password("anything", "not-a-valid-stored-hash") is False


def test_new_session_sets_an_expiry_in_the_future():
    session = new_session(uuid.uuid4())
    assert session.is_expired() is False
    assert len(session.token) > 20


# ------------------------------------------------------------- HTTP tests

@pytest.fixture()
def client(db_conninfo, monkeypatch):
    """Deliberately NOT auto-authenticated (unlike test_api.py's and
    test_api_model_layer.py's `client` fixtures) -- this file tests the
    auth boundary itself."""
    monkeypatch.setenv("PERIOP_DATABASE_URL", db_conninfo)
    import periop_api.deps as deps_module

    deps_module._DEMO_MANIFEST_ID = None

    from periop_api.app import app

    with TestClient(app) as c:
        yield c


def _register_and_login(client, username=None):
    username = username or f"staff-{uuid.uuid4().hex[:12]}"
    resp = client.post("/api/auth/register", json={"username": username, "password": "a-fine-password"})
    assert resp.status_code == 201, resp.text
    resp = client.post("/api/auth/login", json={"username": username, "password": "a-fine-password"})
    assert resp.status_code == 200, resp.text
    return resp.json()["token"], username


def _active_session(client):
    resp = client.post(
        "/api/sessions",
        json={"subject_ref": "pt-auth-1", "age_years": 55, "age_source": "booking_feed"},
    )
    session_id = resp.json()["session_id"]
    client.post(f"/api/sessions/{session_id}/notice")
    client.post(f"/api/sessions/{session_id}/activate")
    return session_id


def test_register_rejects_duplicate_username(client):
    username = f"staff-{uuid.uuid4().hex[:12]}"
    resp = client.post("/api/auth/register", json={"username": username, "password": "a-fine-password"})
    assert resp.status_code == 201
    resp = client.post("/api/auth/register", json={"username": username, "password": "another-password"})
    assert resp.status_code == 409


def test_register_rejects_short_password(client):
    resp = client.post(
        "/api/auth/register", json={"username": f"staff-{uuid.uuid4().hex[:12]}", "password": "short"}
    )
    assert resp.status_code == 422


def test_register_never_returns_the_password_hash(client):
    resp = client.post(
        "/api/auth/register",
        json={"username": f"staff-{uuid.uuid4().hex[:12]}", "password": "a-fine-password"},
    )
    assert "password" not in resp.json()
    assert "password_hash" not in resp.json()


def test_login_rejects_wrong_password(client):
    _, username = _register_and_login(client)
    resp = client.post("/api/auth/login", json={"username": username, "password": "totally-wrong"})
    assert resp.status_code == 401


def test_login_rejects_unknown_username(client):
    resp = client.post("/api/auth/login", json={"username": "no-such-user", "password": "whatever"})
    assert resp.status_code == 401
    # Same failure, same message, whether the username exists or not --
    # never let a caller enumerate valid usernames via the error.
    wrong_pw_resp = client.post(
        "/api/auth/login", json={"username": (_register_and_login(client))[1], "password": "nope"}
    )
    assert wrong_pw_resp.json()["detail"] == resp.json()["detail"]


def test_summary_requires_auth(client):
    session_id = _active_session(client)
    resp = client.get(f"/api/sessions/{session_id}/summary")
    assert resp.status_code == 401


def test_summary_rejects_garbage_token(client):
    session_id = _active_session(client)
    resp = client.get(
        f"/api/sessions/{session_id}/summary", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert resp.status_code == 401


def test_summary_succeeds_with_a_valid_token(client):
    session_id = _active_session(client)
    token, _ = _register_and_login(client)
    resp = client.get(f"/api/sessions/{session_id}/summary", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text


def test_logout_invalidates_the_token(client):
    session_id = _active_session(client)
    token, _ = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get(f"/api/sessions/{session_id}/summary", headers=headers).status_code == 200

    resp = client.post("/api/auth/logout", headers=headers)
    assert resp.status_code == 204

    resp = client.get(f"/api/sessions/{session_id}/summary", headers=headers)
    assert resp.status_code == 401


def test_audit_and_close_and_model_layer_endpoints_require_auth(client):
    session_id = _active_session(client)
    assert client.get(f"/api/sessions/{session_id}/audit").status_code == 401
    assert client.post(f"/api/sessions/{session_id}/close").status_code == 401
    assert client.post(
        f"/api/sessions/{session_id}/hypotheses", json={"content": "x"}
    ).status_code == 401
    assert client.post(
        f"/api/sessions/{session_id}/causal-hypotheses",
        json={"cause": "a", "effect": "b", "confidence": 0.5},
    ).status_code == 401


def test_patient_facing_endpoints_work_without_any_auth(client):
    """Creating a session, acknowledging the notice, activating it, and
    submitting an assertion are all patient-facing -- see
    periop_core.auth's module docstring on the access boundary. None of
    these should need a token."""
    resp = client.post(
        "/api/sessions",
        json={"subject_ref": "pt-no-auth", "age_years": 60, "age_source": "booking_feed"},
    )
    assert resp.status_code == 201, resp.text
    session_id = resp.json()["session_id"]

    assert client.post(f"/api/sessions/{session_id}/notice").status_code == 200
    assert client.post(f"/api/sessions/{session_id}/activate").status_code == 200

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
    # The response is deliberately minimal -- no clinical summary leaks
    # to this unauthenticated caller. See AssertionRecordedResponse.
    body = resp.json()
    assert body["recorded"] is True
    assert "working_facts" not in body
    assert "conflicts" not in body
    assert "gaps" not in body


def test_concepts_and_stateless_tools_work_without_auth(client):
    assert client.get("/api/concepts").status_code == 200
    assert client.post(
        "/api/tools/causal-ecd",
        json={"prior": {"A": 0.5, "B": 0.5}, "likelihoods": {"yes": {"A": 0.9, "B": 0.1}, "no": {"A": 0.1, "B": 0.9}}},
    ).status_code == 200
    assert client.post(
        "/api/tools/attention-working-set", json={"max_size": 1, "candidates": []}
    ).status_code == 200
