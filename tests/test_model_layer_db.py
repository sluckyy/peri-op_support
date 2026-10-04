"""Round-trip tests for periop_core.model_layer_db against a real
Postgres instance (see conftest.py -- skipped if none is reachable).
conftest's db_conninfo fixture applies both 0001_init.sql and
0002_model_layer.sql (see the fixture's MIGRATION_SQL list).
"""
import uuid

import pytest

from periop_core.enums import (
    AssertionState,
    CausalRelationStatus,
    Certainty,
    ContradictionStatus,
    EpistemicLevel,
    HypothesisStatus,
    Materiality,
    ObligationStatus,
    RepairStatus,
    RepairType,
    Salience,
    Speaker,
)
from periop_core.db import insert_release_manifest, insert_session
from periop_core.model_layer import (
    CausalHypothesis,
    Contradiction,
    ConversationalHypothesis,
    GroundedProposition,
    ProspectiveObligation,
    PsychologicalSafetyState,
    RepairRequirement,
    Uncertainty,
)
from periop_core.model_layer_db import (
    get_conversational_hypothesis,
    get_grounded_proposition,
    get_psychological_safety_state,
    get_repair_requirement,
    insert_causal_hypothesis,
    insert_contradiction,
    insert_conversational_hypothesis,
    insert_grounded_proposition,
    insert_prospective_obligation,
    insert_repair_requirement,
    insert_uncertainty,
    list_causal_hypotheses,
    list_contradictions,
    list_conversational_hypotheses,
    list_grounded_propositions,
    list_prospective_obligations,
    list_repair_requirements,
    list_uncertainties,
    update_conversational_hypothesis,
    update_grounded_proposition_superseded,
    update_repair_requirement,
    upsert_psychological_safety_state,
)
from periop_core.models import ConceptReference, ReleaseManifest, Session, SourceReference


def _session(conn):
    manifest = ReleaseManifest(
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
    insert_release_manifest(conn, manifest)
    session = Session(subject_ref="pt-1", manifest_id=manifest.manifest_id)
    insert_session(conn, session)
    return session


def test_grounded_proposition_round_trip(db_conn):
    session = _session(db_conn)
    prop = GroundedProposition(
        session_id=session.session_id,
        content="confirmed penicillin allergy",
        concept=ConceptReference(original_text="penicillin allergy", code="ALL-003"),
        epistemic_level=EpistemicLevel.L4_PATIENT_GROUNDED,
        grounding_evidence=["patient confirmed directly"],
    )
    insert_grounded_proposition(db_conn, prop)
    fetched = list_grounded_propositions(db_conn, session.session_id)
    assert len(fetched) == 1
    assert fetched[0].content == prop.content
    assert fetched[0].concept.code == "ALL-003"
    assert fetched[0].epistemic_level == EpistemicLevel.L4_PATIENT_GROUNDED


def test_grounded_proposition_get_and_mark_superseded(db_conn):
    session = _session(db_conn)
    original = GroundedProposition(
        session_id=session.session_id,
        content="NKDA",
        epistemic_level=EpistemicLevel.L4_PATIENT_GROUNDED,
        grounding_evidence=["patient denied any allergies"],
    )
    insert_grounded_proposition(db_conn, original)
    assert get_grounded_proposition(db_conn, original.proposition_id).superseded_by is None

    replacement = GroundedProposition(
        session_id=session.session_id,
        content="confirmed penicillin allergy (correction)",
        epistemic_level=EpistemicLevel.L4_PATIENT_GROUNDED,
        grounding_evidence=["patient corrected themselves on direct questioning"],
    )
    insert_grounded_proposition(db_conn, replacement)
    update_grounded_proposition_superseded(
        db_conn, original.proposition_id, replacement.proposition_id
    )

    fetched = get_grounded_proposition(db_conn, original.proposition_id)
    assert fetched.superseded_by == replacement.proposition_id


def test_get_grounded_proposition_missing_raises_keyerror(db_conn):
    with pytest.raises(KeyError):
        get_grounded_proposition(db_conn, uuid.uuid4())


def test_conversational_hypothesis_round_trip_and_update(db_conn):
    session = _session(db_conn)
    hyp = ConversationalHypothesis(
        session_id=session.session_id,
        content="possible pulmonary embolism",
        epistemic_level=EpistemicLevel.L3_CLINICAL_HYPOTHESIS,
        confidence=0.4,
    )
    insert_conversational_hypothesis(db_conn, hyp)

    fetched = list_conversational_hypotheses(db_conn, session.session_id)
    assert len(fetched) == 1
    assert fetched[0].status == HypothesisStatus.ACTIVE
    assert fetched[0].confidence == 0.4

    # A real promotion inserts the resulting proposition first -- the FK
    # from conversational_hypothesis.promoted_proposition_id enforces
    # that a hypothesis can't be marked PROMOTED against a proposition
    # that doesn't exist.
    proposition = GroundedProposition(
        session_id=session.session_id,
        content=hyp.content,
        epistemic_level=EpistemicLevel.L4_PATIENT_GROUNDED,
        grounding_evidence=["patient confirmed on direct questioning"],
    )
    insert_grounded_proposition(db_conn, proposition)

    updated = hyp.model_copy(
        update={
            "status": HypothesisStatus.PROMOTED,
            "promoted_proposition_id": proposition.proposition_id,
        }
    )
    update_conversational_hypothesis(db_conn, updated)
    refetched = get_conversational_hypothesis(db_conn, hyp.hypothesis_id)
    assert refetched.status == HypothesisStatus.PROMOTED
    assert refetched.promoted_proposition_id == proposition.proposition_id


def test_prospective_obligation_round_trip(db_conn):
    session = _session(db_conn)
    obligation = ProspectiveObligation(
        session_id=session.session_id,
        content="revisit anticoagulant last-dose timing",
        source="repair:abc",
        priority=Salience.HIGH,
        risk=Salience.HIGH,
    )
    insert_prospective_obligation(db_conn, obligation)
    fetched = list_prospective_obligations(db_conn, session.session_id)
    assert len(fetched) == 1
    assert fetched[0].status == ObligationStatus.PENDING
    assert fetched[0].priority == Salience.HIGH


def test_repair_requirement_round_trip_with_obligation_and_resolve(db_conn):
    session = _session(db_conn)
    obligation = ProspectiveObligation(
        session_id=session.session_id,
        content="revisit later",
        source="repair",
        priority=Salience.MODERATE,
        risk=Salience.MODERATE,
    )
    insert_prospective_obligation(db_conn, obligation)

    repair = RepairRequirement(
        session_id=session.session_id,
        repair_type=RepairType.CONTRADICTION,
        description="patient said two different things",
        materiality=Materiality.MODERATE,
        status=RepairStatus.DEFERRED,
        deferred_reason="will revisit when topic recurs",
        obligation_id=obligation.obligation_id,
    )
    insert_repair_requirement(db_conn, repair)

    fetched = list_repair_requirements(db_conn, session.session_id)
    assert len(fetched) == 1
    assert fetched[0].status == RepairStatus.DEFERRED
    assert fetched[0].obligation_id == obligation.obligation_id

    resolved = repair.model_copy(update={"status": RepairStatus.REPAIRED})
    update_repair_requirement(db_conn, resolved)
    refetched = get_repair_requirement(db_conn, repair.repair_id)
    assert refetched.status == RepairStatus.REPAIRED


def test_contradiction_round_trip(db_conn):
    session = _session(db_conn)
    contradiction = Contradiction(
        session_id=session.session_id,
        description="two interpretations of ambiguous phrasing",
        involved_ids=[uuid.uuid4(), uuid.uuid4()],
    )
    insert_contradiction(db_conn, contradiction)
    fetched = list_contradictions(db_conn, session.session_id)
    assert len(fetched) == 1
    assert fetched[0].status == ContradictionStatus.OPEN
    assert len(fetched[0].involved_ids) == 2


def test_uncertainty_round_trip(db_conn):
    session = _session(db_conn)
    uncertainty = Uncertainty(
        session_id=session.session_id,
        description="unclear whether patient meant left or right knee",
        kind="AMBIGUITY",
    )
    insert_uncertainty(db_conn, uncertainty)
    fetched = list_uncertainties(db_conn, session.session_id)
    assert len(fetched) == 1
    assert fetched[0].resolved is False


def test_causal_hypothesis_round_trip(db_conn):
    session = _session(db_conn)
    causal = CausalHypothesis(
        session_id=session.session_id,
        cause="recent antibiotic course",
        effect="rash",
        confidence=0.6,
        alternatives=["viral exanthem"],
    )
    insert_causal_hypothesis(db_conn, causal)
    fetched = list_causal_hypotheses(db_conn, session.session_id)
    assert len(fetched) == 1
    assert fetched[0].status == CausalRelationStatus.HYPOTHESIS
    assert fetched[0].alternatives == ["viral exanthem"]


def test_psychological_safety_state_upsert(db_conn):
    session = _session(db_conn)
    state = PsychologicalSafetyState(session_id=session.session_id, estimate=0.5)
    upsert_psychological_safety_state(db_conn, state)

    fetched = get_psychological_safety_state(db_conn, session.session_id)
    assert fetched.estimate == 0.5

    updated = state.model_copy(update={"estimate": 0.65, "evidence_signals": ["patient_asked_a_question"]})
    upsert_psychological_safety_state(db_conn, updated)
    refetched = get_psychological_safety_state(db_conn, session.session_id)
    assert refetched.estimate == 0.65
    assert refetched.evidence_signals == ["patient_asked_a_question"]


def test_psychological_safety_state_missing_returns_none(db_conn):
    assert get_psychological_safety_state(db_conn, uuid.uuid4()) is None
