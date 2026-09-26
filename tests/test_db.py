"""Round-trip tests for periop_core.db against a real Postgres instance
(see conftest.py -- skipped if none is reachable)."""
import uuid

from periop_core.db import (
    get_release_manifest,
    get_session,
    insert_agenda_item,
    insert_assertion,
    insert_release_manifest,
    insert_session,
    insert_task,
    list_agenda_items,
    list_assertions,
    list_conflicts,
    list_gaps_for_session,
    list_requirement_states,
    list_tasks,
    list_working_facts,
    replace_reconciliation_state,
    replace_requirement_states_and_gaps,
    update_session,
)
from periop_core.enums import (
    AgendaPriority,
    AssertionState,
    Certainty,
    EligibilityResult,
    GapStatus,
    GapType,
    InformationState,
    SessionStatus,
    Speaker,
    TaskPriority,
    TaskType,
    VerificationState,
)
from periop_core.gap_engine import compute_gaps, evaluate_requirements
from periop_core.models import (
    ConceptReference,
    OpenTask,
    PatientAgendaItem,
    Requirement,
    ReleaseManifest,
    Session,
    SourceReference,
)
from periop_core.reconciliation import reconcile
from periop_core.enums import RequirementClass


def _manifest():
    return ReleaseManifest(
        clinical_dataset_version="1.0.1",
        rules_version="0.1.0",
        terminology_version="unpinned",
        prompt_version="0.1.0",
        extractor_model_id="none",
        language_model_id="none",
        validator_version="0.1.0",
        fhir_mapping_version="0.1.0",
        site_configuration_version="dev",
    )


def test_manifest_round_trip(db_conn):
    manifest = _manifest()
    insert_release_manifest(db_conn, manifest)
    fetched = get_release_manifest(db_conn, manifest.manifest_id)
    assert fetched == manifest


def test_session_round_trip_and_update(db_conn):
    manifest = _manifest()
    insert_release_manifest(db_conn, manifest)
    session = Session(subject_ref="pt-1", manifest_id=manifest.manifest_id)
    insert_session(db_conn, session)

    fetched = get_session(db_conn, session.session_id)
    assert fetched.subject_ref == "pt-1"
    assert fetched.status == SessionStatus.INITIALISE
    assert fetched.eligibility_result is None

    updated = session.model_copy(
        update={"status": SessionStatus.ACTIVE, "eligibility_result": EligibilityResult.ELIGIBLE}
    )
    update_session(db_conn, updated)
    refetched = get_session(db_conn, session.session_id)
    assert refetched.status == SessionStatus.ACTIVE
    assert refetched.eligibility_result == EligibilityResult.ELIGIBLE


def test_assertion_and_reconciliation_round_trip(db_conn):
    manifest = _manifest()
    insert_release_manifest(db_conn, manifest)
    session = Session(subject_ref="pt-1", manifest_id=manifest.manifest_id)
    insert_session(db_conn, session)

    from periop_core.models import Assertion

    patient_report = Assertion(
        session_id=session.session_id,
        subject_ref="pt-1",
        concept=ConceptReference(original_text="penicillin reaction", code="ALL-003"),
        value="throat swelling",
        assertion_state=AssertionState.AFFIRMED,
        source=SourceReference(source_type="PATIENT", speaker=Speaker.PATIENT),
        certainty=Certainty.EXPLICIT,
        provenance={"note": "test"},
    )
    emr_nkda = Assertion(
        session_id=session.session_id,
        subject_ref="pt-1",
        concept=ConceptReference(original_text="NKDA", code="ALL-003"),
        value="NKDA",
        assertion_state=AssertionState.NEGATED,
        source=SourceReference(source_type="EMR", speaker=Speaker.SYSTEM),
        certainty=Certainty.EXPLICIT,
        provenance={"note": "test"},
    )
    insert_assertion(db_conn, patient_report)
    insert_assertion(db_conn, emr_nkda)

    fetched_assertions = list_assertions(db_conn, session.session_id)
    assert {a.assertion_id for a in fetched_assertions} == {
        patient_report.assertion_id,
        emr_nkda.assertion_id,
    }
    assert fetched_assertions[0].concept.code == "ALL-003"

    facts, conflicts = reconcile(fetched_assertions)
    replace_reconciliation_state(db_conn, session.session_id, facts, conflicts)

    fetched_facts = list_working_facts(db_conn, session.session_id)
    fetched_conflicts = list_conflicts(db_conn, session.session_id)

    assert len(fetched_facts) == 1
    assert fetched_facts[0].verification_state == VerificationState.CONFLICTED
    assert set(fetched_facts[0].supporting_assertion_ids) == {
        patient_report.assertion_id,
        emr_nkda.assertion_id,
    }
    assert len(fetched_conflicts) == 1
    assert fetched_conflicts[0].materiality.value == "CRITICAL"


def test_requirement_states_and_gaps_round_trip(db_conn):
    manifest = _manifest()
    insert_release_manifest(db_conn, manifest)
    session = Session(subject_ref="pt-1", manifest_id=manifest.manifest_id)
    insert_session(db_conn, session)

    requirements = {
        "CTX-003": Requirement(
            requirement_id="CTX-003", activation_rule="All patients", requiredness=RequirementClass.M0
        )
    }
    states = evaluate_requirements(session.session_id, requirements, working_facts_by_requirement={})
    gaps = compute_gaps(states, requirements)
    gaps_by_state = {}
    for gap in gaps:
        gaps_by_state.setdefault(gap.requirement_state_id, []).append(gap)

    replace_requirement_states_and_gaps(db_conn, session.session_id, states, gaps_by_state)

    fetched_states = list_requirement_states(db_conn, session.session_id)
    fetched_gaps = list_gaps_for_session(db_conn, session.session_id)

    assert len(fetched_states) == 1
    assert fetched_states[0].information_state == InformationState.NOT_ASKED
    assert len(fetched_gaps) == 1
    assert fetched_gaps[0].gap_type == GapType.MISSING
    assert fetched_gaps[0].status == GapStatus.OPEN


def test_task_and_agenda_item_round_trip(db_conn):
    manifest = _manifest()
    insert_release_manifest(db_conn, manifest)
    session = Session(subject_ref="pt-1", manifest_id=manifest.manifest_id)
    insert_session(db_conn, session)

    task = OpenTask(
        session_id=session.session_id,
        type=TaskType.SAFETY,
        priority=TaskPriority.CRITICAL,
        reason={"why": "possible difficult airway"},
    )
    insert_task(db_conn, task)
    fetched_tasks = list_tasks(db_conn, session.session_id)
    assert len(fetched_tasks) == 1
    assert fetched_tasks[0].blocks_closure() is True

    item = PatientAgendaItem(
        session_id=session.session_id,
        text="worried about waking up during surgery",
        priority=AgendaPriority.HIGH,
    )
    insert_agenda_item(db_conn, item)
    fetched_items = list_agenda_items(db_conn, session.session_id)
    assert len(fetched_items) == 1
    assert fetched_items[0].text == item.text
