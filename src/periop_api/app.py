from __future__ import annotations

import os
import pathlib
import uuid

import psycopg
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from periop_core import audit_db, db, model_layer_db
from periop_core.causal_reasoning import entropy, expected_clinical_discrimination
from periop_core.dataset import default_concept_labels, default_requirements
from periop_core.eligibility import EligibilityContext, evaluate_eligibility
from periop_core.enums import AuditEventType, EligibilityResult, RepairStatus, SessionStatus
from periop_core.epistemic import PromotionNotPermitted, promote_to_grounded_proposition
from periop_core.gap_engine import compute_gaps, evaluate_requirements
from periop_core.humour_policy import HumourContext, is_humour_permitted
from periop_core.model_layer import (
    ConversationalHypothesis,
    ProspectiveObligation,
    PsychologicalSafetyState,
    RepairRequirement,
)
from periop_core.models import Assertion, AuditEvent, ConceptReference, Session, SourceReference
from periop_core.psychological_safety import initial_state as initial_ps_state
from periop_core.psychological_safety import update as update_ps_state
from periop_core.reconciliation import reconcile
from periop_core.safety import evaluate_closure

from periop_api.deps import get_conn, get_demo_manifest
from periop_api.schemas import (
    AddAssertionRequest,
    CausalEcdRequest,
    CausalEcdResponse,
    ClosurePreview,
    ConceptOption,
    CreateHypothesisRequest,
    CreateObligationRequest,
    CreateRepairRequest,
    CreateSessionRequest,
    GapWithLabel,
    HumourCheckRequest,
    HumourCheckResponse,
    PromoteHypothesisRequest,
    PromoteHypothesisResponse,
    PsychologicalSafetySignalRequest,
    SessionSummary,
)

app = FastAPI(
    title="Perioperative Conversational AI -- demo API",
    description=(
        "Demo API over the Phase 1 deterministic core. See "
        "src/periop_api/__init__.py for what is a real code path versus a "
        "documented demo shortcut (notably: POST .../assertions)."
    ),
    version="0.1.0-demo",
)

# Permissive CORS for local/demo use only -- this is not a production
# security posture and is called out here so it isn't mistaken for one.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/concepts", response_model=list[ConceptOption])
def list_concepts():
    requirements = default_requirements()
    labels = default_concept_labels()
    return [
        ConceptOption(
            concept_id=concept_id,
            domain=labels.get(concept_id, {}).get("domain", ""),
            concept=labels.get(concept_id, {}).get("concept", ""),
            patient_question=labels.get(concept_id, {}).get("patient_question", ""),
            requirement_class=requirement.requiredness.value,
        )
        for concept_id, requirement in requirements.items()
    ]


@app.post("/api/sessions", response_model=Session, status_code=201)
def create_session_endpoint(
    body: CreateSessionRequest, conn: psycopg.Connection = Depends(get_conn)
):
    manifest = get_demo_manifest(conn)
    eligibility_ctx = EligibilityContext(
        age_years=body.age_years,
        age_source=body.age_source,
        is_obstetric_procedure=body.is_obstetric_procedure,
        is_obstetric_source=body.is_obstetric_source,
        is_emergency_listing=body.is_emergency_listing,
        is_emergency_source=body.is_emergency_source,
    )
    decision = evaluate_eligibility(eligibility_ctx)
    if decision.result is EligibilityResult.INELIGIBLE:
        raise HTTPException(status_code=422, detail={"reasons": decision.reasons})

    session = Session(
        subject_ref=body.subject_ref,
        encounter_ref=body.encounter_ref,
        procedure_context=body.procedure_context,
        manifest_id=manifest.manifest_id,
        eligibility_result=decision.result,
    )
    db.insert_session(conn, session)
    audit_db.append_event(
        conn,
        AuditEvent(
            session_id=session.session_id,
            event_type=AuditEventType.SESSION_CREATED,
            entity_type="session",
            entity_id=session.session_id,
            payload={"subject_ref": session.subject_ref, "eligibility_result": decision.result.value},
        ),
    )
    return session


@app.post("/api/sessions/{session_id}/notice", response_model=Session)
def acknowledge_notice_endpoint(
    session_id: uuid.UUID, conn: psycopg.Connection = Depends(get_conn)
):
    from datetime import datetime

    session = _get_session_or_404(conn, session_id)
    session = session.model_copy(update={"notice_acknowledged_at": datetime.utcnow()})
    db.update_session(conn, session)
    audit_db.append_event(
        conn,
        AuditEvent(
            session_id=session_id,
            event_type=AuditEventType.NOTICE_ACKNOWLEDGED,
            entity_type="session",
            entity_id=session_id,
            payload={"notice_acknowledged_at": session.notice_acknowledged_at.isoformat()},
        ),
    )
    return session


@app.post("/api/sessions/{session_id}/activate", response_model=Session)
def activate_session_endpoint(session_id: uuid.UUID, conn: psycopg.Connection = Depends(get_conn)):
    session = _get_session_or_404(conn, session_id)
    if not session.has_ai_notice():
        raise HTTPException(
            status_code=409,
            detail="INV-017 violation: acknowledge the AI-role notice before activating",
        )
    if session.status is not SessionStatus.INITIALISE:
        raise HTTPException(status_code=409, detail=f"Cannot activate from status {session.status}")
    session = session.model_copy(update={"status": SessionStatus.ACTIVE})
    db.update_session(conn, session)
    audit_db.append_event(
        conn,
        AuditEvent(
            session_id=session_id,
            event_type=AuditEventType.SESSION_ACTIVATED,
            entity_type="session",
            entity_id=session_id,
            payload={},
        ),
    )
    return session


@app.post("/api/sessions/{session_id}/assertions", response_model=SessionSummary)
def add_assertion_endpoint(
    session_id: uuid.UUID,
    body: AddAssertionRequest,
    conn: psycopg.Connection = Depends(get_conn),
):
    session = _get_session_or_404(conn, session_id)
    labels = default_concept_labels()
    concept_label = labels.get(body.concept_code, {}).get("concept", body.concept_code)

    assertion_kwargs = dict(
        session_id=session_id,
        subject_ref=session.subject_ref,
        concept=ConceptReference(
            original_text=body.concept_text or concept_label, code=body.concept_code
        ),
        value=body.value,
        assertion_state=body.assertion_state,
        source=SourceReference(source_type=body.source_type, speaker=body.speaker),
        certainty=body.certainty,
        provenance={"entered_via": "demo API -- see periop_api/__init__.py"},
    )
    if body.assertion_time is not None:
        # Demo-only backdating -- see AddAssertionRequest.assertion_time.
        assertion_kwargs["assertion_time"] = body.assertion_time
    assertion = Assertion(**assertion_kwargs)
    db.insert_assertion(conn, assertion)
    audit_db.append_event(
        conn,
        AuditEvent(
            session_id=session_id,
            event_type=AuditEventType.ASSERTION_ADDED,
            entity_type="assertion",
            entity_id=assertion.assertion_id,
            payload={
                "concept_code": body.concept_code,
                "assertion_state": assertion.assertion_state.value,
                "source_type": assertion.source.source_type,
                "speaker": assertion.source.speaker.value,
            },
        ),
    )

    return _recompute_and_summarise(conn, session_id)


@app.get("/api/sessions/{session_id}/summary", response_model=SessionSummary)
def get_summary_endpoint(session_id: uuid.UUID, conn: psycopg.Connection = Depends(get_conn)):
    _get_session_or_404(conn, session_id)
    return _recompute_and_summarise(conn, session_id)


@app.post("/api/sessions/{session_id}/close", response_model=SessionSummary)
def close_session_endpoint(session_id: uuid.UUID, conn: psycopg.Connection = Depends(get_conn)):
    session = _get_session_or_404(conn, session_id)
    summary = _recompute_and_summarise(conn, session_id)

    if summary.closure_preview.outcome.value == "BLOCKED":
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Cannot close: blocking conditions present",
                "blocking_reasons": summary.closure_preview.blocking_reasons,
            },
        )

    session = session.model_copy(update={"status": SessionStatus.COMPLETE})
    db.update_session(conn, session)
    audit_db.append_event(
        conn,
        AuditEvent(
            session_id=session_id,
            event_type=AuditEventType.SESSION_CLOSED,
            entity_type="session",
            entity_id=session_id,
            payload={"closure_outcome": summary.closure_preview.outcome.value},
        ),
    )
    summary.session = session
    return summary


@app.get("/api/sessions/{session_id}/audit", response_model=list[AuditEvent])
def get_audit_lineage_endpoint(session_id: uuid.UUID, conn: psycopg.Connection = Depends(get_conn)):
    """SVC-014's `getLineage`. Only covers the Phase 1 core lifecycle
    events listed in periop_core.enums.AuditEventType -- see README."""
    _get_session_or_404(conn, session_id)
    return audit_db.get_lineage(conn, session_id)


@app.post("/api/sessions/{session_id}/hypotheses", response_model=ConversationalHypothesis)
def create_hypothesis_endpoint(
    session_id: uuid.UUID,
    body: CreateHypothesisRequest,
    conn: psycopg.Connection = Depends(get_conn),
):
    """v1.1 §6A -- a conversational hypothesis at L1/L2/L3, not yet
    clinically grounded. See periop_core.model_layer.ConversationalHypothesis."""
    _get_session_or_404(conn, session_id)
    try:
        hypothesis = ConversationalHypothesis(
            session_id=session_id,
            content=body.content,
            epistemic_level=body.epistemic_level,
            supporting_observations=body.supporting_observations,
            confidence=body.confidence,
        )
    except ValueError as exc:
        # e.g. epistemic_level of L4+ (Table 9: "cannot be projected as fact")
        raise HTTPException(status_code=422, detail=str(exc)) from None
    model_layer_db.insert_conversational_hypothesis(conn, hypothesis)
    return hypothesis


@app.post(
    "/api/sessions/{session_id}/hypotheses/{hypothesis_id}/promote",
    response_model=PromoteHypothesisResponse,
)
def promote_hypothesis_endpoint(
    session_id: uuid.UUID,
    hypothesis_id: uuid.UUID,
    body: PromoteHypothesisRequest,
    conn: psycopg.Connection = Depends(get_conn),
):
    """v1.1 §6A.3 -- enforces the epistemic ladder's promotion gates for
    real (periop_core.epistemic.can_promote): crossing into L4+ requires
    grounding_evidence; crossing into L6 requires
    has_clinician_adjudication. Returns 409 with the specific reasons on
    failure rather than silently doing nothing."""
    _get_session_or_404(conn, session_id)
    try:
        hypothesis = model_layer_db.get_conversational_hypothesis(conn, hypothesis_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Hypothesis {hypothesis_id} not found") from None

    try:
        updated_hypothesis, proposition = promote_to_grounded_proposition(
            hypothesis,
            target_level=body.target_level,
            grounding_evidence=body.grounding_evidence,
            has_clinician_adjudication=body.has_clinician_adjudication,
        )
    except PromotionNotPermitted as exc:
        raise HTTPException(status_code=409, detail={"reasons": exc.reasons}) from None

    model_layer_db.insert_grounded_proposition(conn, proposition)
    model_layer_db.update_conversational_hypothesis(conn, updated_hypothesis)
    return PromoteHypothesisResponse(hypothesis=updated_hypothesis, proposition=proposition)


@app.post("/api/sessions/{session_id}/obligations", response_model=ProspectiveObligation)
def create_obligation_endpoint(
    session_id: uuid.UUID,
    body: CreateObligationRequest,
    conn: psycopg.Connection = Depends(get_conn),
):
    _get_session_or_404(conn, session_id)
    obligation = ProspectiveObligation(
        session_id=session_id,
        content=body.content,
        source=body.source,
        priority=body.priority,
        risk=body.risk,
        trigger=body.trigger,
        deadline=body.deadline,
    )
    model_layer_db.insert_prospective_obligation(conn, obligation)
    return obligation


@app.post("/api/sessions/{session_id}/repairs", response_model=RepairRequirement)
def create_repair_endpoint(
    session_id: uuid.UUID,
    body: CreateRepairRequest,
    conn: psycopg.Connection = Depends(get_conn),
):
    """v1.1 §6A.15 -- 'repair is mandatory when material misunderstanding
    is detected' and 'deferral creates an obligation when the issue
    remains relevant'. Constructing a DEFERRED RepairRequirement without
    a reason and a linked obligation fails with 422 (the pydantic
    validator on RepairRequirement itself, not a hand-written check
    here) -- `create_obligation` lets the caller supply that obligation's
    fields in the same request rather than needing two round-trips."""
    _get_session_or_404(conn, session_id)

    obligation_id = body.obligation_id
    if body.create_obligation is not None:
        obligation = ProspectiveObligation(
            session_id=session_id,
            content=body.create_obligation.content,
            source=body.create_obligation.source,
            priority=body.create_obligation.priority,
            risk=body.create_obligation.risk,
            trigger=body.create_obligation.trigger,
            deadline=body.create_obligation.deadline,
        )
        model_layer_db.insert_prospective_obligation(conn, obligation)
        obligation_id = obligation.obligation_id

    try:
        repair = RepairRequirement(
            session_id=session_id,
            repair_type=body.repair_type,
            description=body.description,
            materiality=body.materiality,
            status=body.status,
            ai_self_repair=body.ai_self_repair,
            deferred_reason=body.deferred_reason,
            obligation_id=obligation_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    model_layer_db.insert_repair_requirement(conn, repair)
    return repair


@app.post("/api/sessions/{session_id}/repairs/{repair_id}/resolve", response_model=RepairRequirement)
def resolve_repair_endpoint(
    session_id: uuid.UUID, repair_id: uuid.UUID, conn: psycopg.Connection = Depends(get_conn)
):
    _get_session_or_404(conn, session_id)
    try:
        repair = model_layer_db.get_repair_requirement(conn, repair_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Repair {repair_id} not found") from None

    resolved = repair.model_copy(update={"status": RepairStatus.REPAIRED})
    model_layer_db.update_repair_requirement(conn, resolved)
    return resolved


@app.post(
    "/api/sessions/{session_id}/psychological-safety/signal",
    response_model=PsychologicalSafetyState,
)
def apply_psychological_safety_signal_endpoint(
    session_id: uuid.UUID,
    body: PsychologicalSafetySignalRequest,
    conn: psycopg.Connection = Depends(get_conn),
):
    """v1.1 §6A.7. See periop_core.psychological_safety's module
    docstring before treating the result as anything more than a bounded,
    inspectable heuristic."""
    _get_session_or_404(conn, session_id)
    current = model_layer_db.get_psychological_safety_state(conn, session_id)
    if current is None:
        current = initial_ps_state(session_id)
    try:
        updated = update_ps_state(current, body.signal_names)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    model_layer_db.upsert_psychological_safety_state(conn, updated)
    return updated


@app.post("/api/sessions/{session_id}/humour/check", response_model=HumourCheckResponse)
def check_humour_endpoint(session_id: uuid.UUID, body: HumourCheckRequest):
    """v1.1 §6A.8. Stateless -- nothing is persisted; this just runs the
    permission gate against the supplied context. `feature_enabled`
    defaults to False (Table 13: off by default until evaluated)."""
    permitted, reasons = is_humour_permitted(HumourContext(**body.model_dump()))
    return HumourCheckResponse(permitted=permitted, reasons=reasons)


@app.post("/api/tools/causal-ecd", response_model=CausalEcdResponse)
def causal_ecd_endpoint(body: CausalEcdRequest):
    """v1.1 §6A.10 -- a standalone calculator over the real
    Shannon-entropy machinery in periop_core.causal_reasoning, not tied
    to any session's stored CausalHypothesis rows. Useful for exploring
    what makes a question discriminating without needing a full
    likelihood model wired up to real clinical data."""
    try:
        prior_entropy = entropy(body.prior)
        ecd = expected_clinical_discrimination(body.prior, body.likelihoods)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return CausalEcdResponse(
        prior_entropy=prior_entropy,
        expected_posterior_entropy=prior_entropy - ecd,
        ecd=ecd,
    )


def _get_session_or_404(conn: psycopg.Connection, session_id: uuid.UUID) -> Session:
    try:
        return db.get_session(conn, session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found") from None


def _recompute_and_summarise(conn: psycopg.Connection, session_id: uuid.UUID) -> SessionSummary:
    """Re-run reconciliation and gap evaluation over the session's full
    assertion history and persist the (recomputed, not accumulated --
    see periop_core.db module docstring) derived state."""
    session = db.get_session(conn, session_id)
    requirements = default_requirements()
    labels = default_concept_labels()

    assertions = db.list_assertions(conn, session_id)
    facts, conflicts = reconcile(assertions)
    db.replace_reconciliation_state(conn, session_id, facts, conflicts)

    working_facts_by_requirement = {
        fact.concept.code: fact for fact in facts if fact.concept.code in requirements
    }
    states = evaluate_requirements(session_id, requirements, working_facts_by_requirement)
    gaps = compute_gaps(states, requirements)
    gaps_by_state: dict[uuid.UUID, list] = {}
    for gap in gaps:
        gaps_by_state.setdefault(gap.requirement_state_id, []).append(gap)
    db.replace_requirement_states_and_gaps(conn, session_id, states, gaps_by_state)

    state_by_id = {s.requirement_state_id: s for s in states}
    gaps_with_labels = []
    for gap in sorted(gaps, key=lambda g: g.priority_score, reverse=True):
        req_state = state_by_id[gap.requirement_state_id]
        label = labels.get(req_state.requirement_id, {})
        gaps_with_labels.append(
            GapWithLabel(
                gap=gap,
                requirement_id=req_state.requirement_id,
                domain=label.get("domain"),
                concept=label.get("concept"),
            )
        )

    tasks = db.list_tasks(conn, session_id)
    agenda_items = db.list_agenda_items(conn, session_id)

    # v1.1 Model Layer state -- see periop_core.model_layer_db. Not
    # recomputed like facts/gaps above (nothing derives these from
    # assertions yet; there's no Orchestrator), just read back as-is.
    hypotheses = model_layer_db.list_conversational_hypotheses(conn, session_id)
    propositions = model_layer_db.list_grounded_propositions(conn, session_id)
    obligations = model_layer_db.list_prospective_obligations(conn, session_id)
    repairs = model_layer_db.list_repair_requirements(conn, session_id)
    psychological_safety = model_layer_db.get_psychological_safety_state(conn, session_id)

    closure = evaluate_closure(
        open_tasks=tasks,
        agenda_items=agenda_items,
        conflicts=conflicts,
        repair_requirements=repairs,
    )

    return SessionSummary(
        session=session,
        working_facts=facts,
        conflicts=conflicts,
        requirement_states=states,
        gaps=gaps_with_labels,
        tasks=tasks,
        agenda_items=agenda_items,
        closure_preview=ClosurePreview(
            outcome=closure.outcome,
            blocking_reasons=closure.blocking_reasons,
            open_action_reasons=closure.open_action_reasons,
        ),
        hypotheses=hypotheses,
        propositions=propositions,
        obligations=obligations,
        repairs=repairs,
        psychological_safety=psychological_safety,
    )


# Serve the built frontend (see Dockerfile) if present. Mounted last so it
# never shadows the /api/* routes registered above -- Starlette matches
# routes in registration order. Absent in plain local API-only dev (Vite's
# own dev server + proxy serves the frontend instead), so this is guarded
# rather than assumed.
_frontend_dist = os.environ.get(
    "PERIOP_FRONTEND_DIST",
    str(pathlib.Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"),
)
if os.path.isdir(_frontend_dist):
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="frontend")
