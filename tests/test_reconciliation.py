"""Exercises periop_core.reconciliation against scenarios modelled on
docs/exports/reconciliation_test_cases.csv (REC-T001, REC-T005-style).

Scope note: as documented in reconciliation.py, this implementation now
performs freshness assessment (step 3, see the tests below) but not
fitness-based tie-breaking (step 4 proper) or auto-resolution (step 7).
The REC-T005 (stale-vs-current smoking status) test below asserts the
CURRENT, honestly-limited behaviour -- it's a *disagreement* between an
old and a new assertion, which step 3 deliberately does not touch (that's
step 7's job); it reports a conflict rather than correctly resolving to
"current ex-smoker" the way the full algorithm should. That gap is
intentional and tracked, not a bug this test is hiding.
"""
import uuid
from datetime import datetime, timedelta

from periop_core.enums import AssertionState, Certainty, Materiality, Speaker, VerificationState
from periop_core.models import Assertion, ConceptReference, SourceReference
from periop_core.reconciliation import reconcile


def _assertion(session_id, concept_code, state, value, source_type, speaker, assertion_time=None):
    kwargs = dict(
        session_id=session_id,
        subject_ref="pt-1",
        concept=ConceptReference(original_text=concept_code, code=concept_code),
        value=value,
        assertion_state=state,
        source=SourceReference(source_type=source_type, speaker=speaker),
        certainty=Certainty.EXPLICIT,
        provenance={"note": "test"},
    )
    if assertion_time is not None:
        kwargs["assertion_time"] = assertion_time
    return Assertion(**kwargs)


def test_agreeing_assertions_produce_single_confirmed_working_fact():
    session_id = uuid.uuid4()
    assertions = [
        _assertion(session_id, "CTX-003", AssertionState.AFFIRMED, "left knee replacement",
                   "PATIENT", Speaker.PATIENT),
        _assertion(session_id, "CTX-003", AssertionState.AFFIRMED, "left knee replacement",
                   "BOOKING_SYSTEM", Speaker.SYSTEM),
    ]

    facts, conflicts = reconcile(assertions)

    assert len(facts) == 1
    assert len(conflicts) == 0
    assert facts[0].verification_state == VerificationState.UNCONFIRMED
    assert set(facts[0].supporting_assertion_ids) == {a.assertion_id for a in assertions}


def test_rec_t001_style_allergy_presence_absence_conflict_is_critical_and_preserves_both():
    """REC-T001: patient reports severe penicillin reaction absent from EMR.
    Expected: SAFETY_CRITICAL presence/absence conflict; neither assertion
    discarded (the EMR's NKDA is never allowed to silently win)."""
    session_id = uuid.uuid4()
    patient_report = _assertion(
        session_id, "ALL-003", AssertionState.AFFIRMED, "throat swelling after penicillin",
        "PATIENT", Speaker.PATIENT,
    )
    emr_nkda = _assertion(
        session_id, "ALL-003", AssertionState.NEGATED, "NKDA", "EMR", Speaker.SYSTEM,
    )

    facts, conflicts = reconcile([patient_report, emr_nkda])

    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict.materiality == Materiality.CRITICAL
    assert conflict.can_auto_resolve() is False
    assert set(conflict.assertion_ids) == {patient_report.assertion_id, emr_nkda.assertion_id}

    assert len(facts) == 1
    assert facts[0].verification_state == VerificationState.CONFLICTED
    # Neither assertion is discarded -- both remain referenced.
    assert set(facts[0].supporting_assertion_ids) == {
        patient_report.assertion_id,
        emr_nkda.assertion_id,
    }


def test_airway_prefix_conflict_is_critical():
    """AIR- (airway/dental/anatomical history, e.g. limited mouth opening,
    previous difficult airway) must be CRITICAL like ALL-/ANAES-/MED- --
    the Escalation Classes table (ESC-003) and Conflict Taxonomy both
    name airway alongside allergy and anaesthetic safety, so a presence/
    absence disagreement here must block auto-resolution the same way."""
    session_id = uuid.uuid4()
    patient_report = _assertion(
        session_id, "AIR-001", AssertionState.AFFIRMED, "limited mouth opening",
        "PATIENT", Speaker.PATIENT,
    )
    emr_denial = _assertion(
        session_id, "AIR-001", AssertionState.NEGATED, "no airway concerns", "EMR", Speaker.SYSTEM,
    )

    facts, conflicts = reconcile([patient_report, emr_denial])

    assert len(conflicts) == 1
    assert conflicts[0].materiality == Materiality.CRITICAL
    assert conflicts[0].can_auto_resolve() is False


def test_rec_t005_style_stale_vs_current_smoking_reports_as_conflict_not_resolved():
    """REC-T005 in the full algorithm should resolve to 'current ex-smoker
    with dated history' via the freshness step (step 3), which this
    minimal engine does not implement. This test pins down the current,
    more conservative behaviour (an open MODERATE conflict) so the gap is
    visible in the test suite rather than silently papered over."""
    session_id = uuid.uuid4()
    old_record = _assertion(
        session_id, "PSY-018", AssertionState.AFFIRMED, "current smoker", "EMR", Speaker.SYSTEM,
    )
    patient_now = _assertion(
        session_id, "PSY-018", AssertionState.AFFIRMED, "quit 2024", "PATIENT", Speaker.PATIENT,
    )

    facts, conflicts = reconcile([old_record, patient_now])

    assert len(conflicts) == 1
    assert conflicts[0].materiality == Materiality.MODERATE  # not in the critical-prefix list
    assert facts[0].verification_state == VerificationState.CONFLICTED


def test_old_agreeing_assertion_is_marked_stale_not_left_unconfirmed_forever():
    """Step 3 (assess freshness): a single-source (or agreeing) fact that
    hasn't been reasserted in a long time must not silently look the same
    as one confirmed a minute ago -- that's the whole point of the
    'stale data cannot silently satisfy a current-data requirement'
    safety invariant."""
    session_id = uuid.uuid4()
    now = datetime(2026, 1, 1)
    old_assertion = _assertion(
        session_id, "CUR-002", AssertionState.AFFIRMED, "no recent change", "PATIENT",
        Speaker.PATIENT, assertion_time=now - timedelta(days=400),
    )

    facts, conflicts = reconcile([old_assertion], now=now)

    assert conflicts == []
    assert facts[0].verification_state == VerificationState.STALE
    assert facts[0].freshness["classification"] == "STALE"


def test_recent_agreeing_assertion_is_not_stale():
    session_id = uuid.uuid4()
    now = datetime(2026, 1, 1)
    recent = _assertion(
        session_id, "CUR-002", AssertionState.AFFIRMED, "no recent change", "PATIENT",
        Speaker.PATIENT, assertion_time=now - timedelta(days=5),
    )

    facts, conflicts = reconcile([recent], now=now)

    assert facts[0].verification_state == VerificationState.UNCONFIRMED
    assert facts[0].freshness["classification"] == "CURRENT"


def test_evergreen_domain_is_never_marked_stale_even_when_very_old():
    """Allergy (and family history / identity) are 'longitudinal' per the
    Source Authority Matrix -- an old confirmed penicillin allergy is not
    a data-quality problem the way an old vitals reading would be."""
    session_id = uuid.uuid4()
    now = datetime(2026, 1, 1)
    old_allergy = _assertion(
        session_id, "ALL-003", AssertionState.AFFIRMED, "penicillin", "PATIENT",
        Speaker.PATIENT, assertion_time=now - timedelta(days=3650),
    )

    facts, conflicts = reconcile([old_allergy], now=now)

    assert facts[0].verification_state == VerificationState.UNCONFIRMED
    assert facts[0].freshness["classification"] == "EXEMPT"


def test_no_assertion_is_ever_dropped():
    session_id = uuid.uuid4()
    assertions = [
        _assertion(session_id, "MED-010", AssertionState.AFFIRMED, "5mg", "PATIENT", Speaker.PATIENT),
        _assertion(session_id, "MED-010", AssertionState.AFFIRMED, "10mg", "EMR", Speaker.SYSTEM),
        _assertion(session_id, "CARD-014", AssertionState.NEGATED, None, "PATIENT", Speaker.PATIENT),
    ]

    facts, conflicts = reconcile(assertions)

    referenced_ids = set()
    for fact in facts:
        referenced_ids.update(fact.supporting_assertion_ids)
        referenced_ids.update(fact.dissenting_assertion_ids)
    for conflict in conflicts:
        referenced_ids.update(conflict.assertion_ids)

    assert referenced_ids == {a.assertion_id for a in assertions}
