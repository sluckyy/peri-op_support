"""Tests for the clinician-reviewed question skip map
(periop_core.skip_map) and how the gap engine applies it."""
import uuid
from datetime import datetime, timedelta

import pytest

from periop_core import skip_map
from periop_core.dataset import default_requirements
from periop_core.enums import AssertionState, Certainty, InformationState, Speaker, VerificationState
from periop_core.gap_engine import compute_gaps, evaluate_requirements, negated_concepts
from periop_core.models import Assertion, ConceptReference, SourceReference
from periop_core.reconciliation import reconcile
from periop_core.skip_map import SkipRule, choose_next_target, load_skip_rules, skipped_children, validate_rules

SEIZURE_RULE = SkipRule("T-1", ("NEURO-004",), ("NEURO-005",), "test", "APPROVED", "Dr Test")
DIABETES_RULE = SkipRule("T-2", ("ENDO-001", "MED-010"), ("ENDO-002", "ENDO-003"), "test", "APPROVED", "Dr Test")


# ------------------------------------------------------------ the file

def test_shipped_skip_map_loads_and_validates():
    rules = load_skip_rules()
    assert len(rules) >= 20
    assert all(r.rationale for r in rules)


def test_shipped_rules_never_skip_a_mandatory_question():
    requirements = default_requirements()
    for rule in load_skip_rules():
        for child in rule.children:
            assert requirements[child].requiredness.value not in ("M0", "M1"), (rule.rule_id, child)


# ------------------------------------------------------------ validation

@pytest.mark.parametrize("rule, message", [
    (SkipRule("X", ("NEURO-004",), ("NOPE-999",), "r", "PROPOSED"), "unknown concept"),
    (SkipRule("X", ("MED-001",), ("MED-010",), "r", "PROPOSED"), "must always be asked"),
    (SkipRule("X", ("NEURO-004",), ("NEURO-005",), "r", "APPROVED"), "name who approved"),
    (SkipRule("X", ("NEURO-004",), ("NEURO-005",), "r", "MAYBE"), "unknown status"),
])
def test_validator_rejects_bad_rules(rule, message):
    with pytest.raises(ValueError, match=message):
        validate_rules([rule], default_requirements())


def test_validator_rejects_chains():
    a = SkipRule("A", ("ANAES-001",), ("ANAES-003",), "r", "PROPOSED")
    b = SkipRule("B", ("ANAES-003",), ("ANAES-013",), "r", "PROPOSED")
    with pytest.raises(ValueError, match="no chains"):
        validate_rules([a, b], default_requirements())


def test_only_approved_rules_take_effect(tmp_path):
    csv_path = tmp_path / "map.csv"
    csv_path.write_text(
        "rule_id,skip_when_all_negated,children,rationale,status,approved_by,approved_on\n"
        "A,NEURO-004,NEURO-005,r,PROPOSED,,\n"
        "B,RES-010,RES-011,r,APPROVED,Dr Test,2026-11-27\n"
    )
    rules = load_skip_rules(csv_path)
    assert [r.rule_id for r in rules if r.approved] == ["B"]


# ------------------------------------------------------------ applying it

def test_skipped_children_requires_every_parent_negated():
    assert skipped_children([DIABETES_RULE], {"ENDO-001"}) == {}
    assert skipped_children([DIABETES_RULE], {"ENDO-001", "MED-010"}) == {
        "ENDO-002": {"ENDO-001", "MED-010"},
        "ENDO-003": {"ENDO-001", "MED-010"},
    }


def _assertion(session_id, code, state, source="PATIENT", when=None):
    kwargs = dict(
        session_id=session_id, subject_ref="pt", concept=ConceptReference(original_text=code, code=code),
        value=None, assertion_state=state, source=SourceReference(source_type=source, speaker=Speaker.PATIENT),
        certainty=Certainty.EXPLICIT, provenance={"note": "test"},
    )
    if when is not None:
        kwargs["assertion_time"] = when
    return Assertion(**kwargs)


def _states(assertions, rules):
    session_id = assertions[0].session_id
    facts, _ = reconcile(assertions)
    requirements = default_requirements()
    by_req = {f.concept.code: f for f in facts if f.concept.code in requirements}
    skipped = skipped_children(rules, negated_concepts(facts, assertions))
    not_applicable = {c: [a for p in ps for a in by_req[p].supporting_assertion_ids] for c, ps in skipped.items()}
    states = evaluate_requirements(session_id, requirements, by_req, not_applicable)
    return {s.requirement_id: s for s in states}, compute_gaps(states, requirements)


def test_clear_no_makes_follow_up_not_applicable_with_evidence_and_no_gap():
    sid = uuid.uuid4()
    no_seizures = _assertion(sid, "NEURO-004", AssertionState.NEGATED)
    states, gaps = _states([no_seizures], [SEIZURE_RULE])
    child = states["NEURO-005"]
    assert child.information_state == InformationState.NOT_APPLICABLE
    assert child.evidence_refs == [no_seizures.assertion_id]
    assert child.requirement_state_id not in {g.requirement_state_id for g in gaps}


@pytest.mark.parametrize("state", [
    AssertionState.AFFIRMED, AssertionState.UNCERTAIN, AssertionState.UNKNOWN, AssertionState.DECLINED,
])
def test_anything_but_a_clear_no_keeps_the_follow_up(state):
    sid = uuid.uuid4()
    states, _ = _states([_assertion(sid, "NEURO-004", state)], [SEIZURE_RULE])
    assert states["NEURO-005"].information_state == InformationState.NOT_ASKED


def test_conflicting_parent_keeps_the_follow_up():
    sid = uuid.uuid4()
    states, _ = _states([
        _assertion(sid, "NEURO-004", AssertionState.NEGATED),
        _assertion(sid, "NEURO-004", AssertionState.AFFIRMED, source="EMR"),
    ], [SEIZURE_RULE])
    assert states["NEURO-004"].information_state == InformationState.CONFLICTING
    assert states["NEURO-005"].information_state == InformationState.NOT_ASKED


def test_stale_parent_keeps_the_follow_up():
    sid = uuid.uuid4()
    old = _assertion(sid, "NEURO-004", AssertionState.NEGATED, when=datetime.utcnow() - timedelta(days=400))
    facts, _ = reconcile([old])
    assert facts[0].verification_state == VerificationState.STALE
    states, _ = _states([old], [SEIZURE_RULE])
    assert states["NEURO-005"].information_state == InformationState.NOT_ASKED


def test_a_follow_up_with_its_own_answer_is_never_overridden():
    sid = uuid.uuid4()
    states, _ = _states([
        _assertion(sid, "NEURO-004", AssertionState.NEGATED),
        _assertion(sid, "NEURO-005", AssertionState.AFFIRMED),
    ], [SEIZURE_RULE])
    assert states["NEURO-005"].information_state == InformationState.KNOWN_UNCONFIRMED


def test_unapproved_rules_do_nothing():
    sid = uuid.uuid4()
    proposed = SkipRule("T-3", ("NEURO-004",), ("NEURO-005",), "test", "PROPOSED")
    approved = tuple(r for r in [proposed] if r.approved)
    states, _ = _states([_assertion(sid, "NEURO-004", AssertionState.NEGATED)], approved)
    assert states["NEURO-005"].information_state == InformationState.NOT_ASKED


# ------------------------------------------------------------ ordering

def test_follow_up_waits_for_its_parent_even_if_higher_priority():
    pregnancy = SkipRule("T-4", ("GOAL-009",), ("GOAL-010",), "test", "APPROVED", "Dr Test")
    # GOAL-010 (C1) outranks GOAL-009 (C4) in gap priority.
    candidates = ["GOAL-010", "GOAL-009"]
    assert choose_next_target(candidates, answered=set(), rules=[pregnancy]) == "GOAL-009"
    assert choose_next_target(["GOAL-010"], answered={"GOAL-009"}, rules=[pregnancy]) == "GOAL-010"


def test_ordering_falls_back_when_everything_is_waiting():
    pregnancy = SkipRule("T-4", ("GOAL-009",), ("GOAL-010",), "test", "APPROVED", "Dr Test")
    assert choose_next_target(["GOAL-010"], answered=set(), rules=[pregnancy]) == "GOAL-010"
    assert choose_next_target([], answered=set(), rules=[pregnancy]) is None


# ------------------------------------------------------------ via the API

def test_summary_and_interviewer_respect_an_approved_rule(db_conninfo, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("PERIOP_DATABASE_URL", db_conninfo)
    monkeypatch.setattr(skip_map, "approved_skip_rules", lambda: (SEIZURE_RULE,))
    import periop_api.deps as deps_module

    deps_module._DEMO_MANIFEST_ID = None
    from periop_api.app import app

    with TestClient(app) as client:
        username = f"staff-{uuid.uuid4().hex[:12]}"
        client.post("/api/auth/register", json={"username": username, "password": "a-fine-password"})
        token = client.post("/api/auth/login", json={"username": username, "password": "a-fine-password"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        sid = client.post("/api/sessions", json={"subject_ref": "pt-skip", "age_years": 50,
                                                  "age_source": "booking_feed"}).json()["session_id"]
        client.post(f"/api/sessions/{sid}/notice")
        client.post(f"/api/sessions/{sid}/activate")
        resp = client.post(f"/api/sessions/{sid}/assertions", json={
            "concept_code": "NEURO-004", "assertion_state": "NEGATED", "source_type": "PATIENT"})
        assert resp.status_code == 200, resp.text

        summary = client.get(f"/api/sessions/{sid}/summary", headers=headers).json()
    states = {s["requirement_id"]: s for s in summary["requirement_states"]}
    assert states["NEURO-005"]["information_state"] == "NOT_APPLICABLE"
    assert "NEURO-005" not in {g["requirement_id"] for g in summary["gaps"]}
