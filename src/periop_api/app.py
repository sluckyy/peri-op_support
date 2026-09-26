from __future__ import annotations

import os
import pathlib
import uuid

import psycopg
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from periop_core import db
from periop_core.dataset import default_concept_labels, default_requirements
from periop_core.eligibility import EligibilityContext, evaluate_eligibility
from periop_core.enums import EligibilityResult, SessionStatus
from periop_core.gap_engine import compute_gaps, evaluate_requirements
from periop_core.models import Assertion, ConceptReference, Session, SourceReference
from periop_core.reconciliation import reconcile
from periop_core.safety import evaluate_closure

from periop_api.deps import get_conn, get_demo_manifest
from periop_api.schemas import (
    AddAssertionRequest,
    ClosurePreview,
    ConceptOption,
    CreateSessionRequest,
    GapWithLabel,
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
    return session


@app.post("/api/sessions/{session_id}/notice", response_model=Session)
def acknowledge_notice_endpoint(
    session_id: uuid.UUID, conn: psycopg.Connection = Depends(get_conn)
):
    from datetime import datetime

    session = _get_session_or_404(conn, session_id)
    session = session.model_copy(update={"notice_acknowledged_at": datetime.utcnow()})
    db.update_session(conn, session)
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

    assertion = Assertion(
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
    db.insert_assertion(conn, assertion)

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
    summary.session = session
    return summary


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
    closure = evaluate_closure(open_tasks=tasks, agenda_items=agenda_items, conflicts=conflicts)

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
