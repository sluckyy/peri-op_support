from __future__ import annotations

import os
import pathlib
import uuid

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from periop_core import audit_db, auth_db, conflict_review_db, db, model_layer_db
from periop_core.attention import AttentionCandidate, AttentionFactors, select_working_set
from periop_core.auth import User, hash_password, new_session, verify_password
from periop_core.causal_reasoning import entropy, expected_clinical_discrimination
from periop_core.dataset import default_concept_labels, default_requirements
from periop_core.eligibility import EligibilityContext, evaluate_eligibility
from periop_core.enums import (
    ActionType,
    AuditEventType,
    ContradictionStatus,
    EligibilityResult,
    InterviewActionStatus,
    Modality,
    RepairStatus,
    SessionStatus,
    Speaker,
)
from periop_core.epistemic import PromotionNotPermitted, promote_to_grounded_proposition
from periop_core.gap_engine import compute_gaps, evaluate_requirements
from periop_core.humour_policy import HumourContext, is_humour_permitted
from periop_core.interview_llm import (
    PROMPT_VERSION,
    InterviewerUnavailable,
    extract_answer,
    llm_model,
    realise_question,
    validate_candidate,
)
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
from periop_core.model_layer_gate import (
    find_dependents,
    reference_string,
    required_repair_for_correction,
)
from periop_core.models import (
    Assertion,
    AuditEvent,
    ConceptReference,
    ConflictReview,
    ConflictReviewSide,
    InterviewAction,
    Session,
    SourceReference,
    Turn,
)
from periop_core.psychological_safety import initial_state as initial_ps_state
from periop_core.psychological_safety import update as update_ps_state
from periop_core.reconciliation import reconcile
from periop_core.safety import evaluate_closure

from periop_api.deps import get_conn, get_demo_manifest, get_llm_client
from periop_api.schemas import (
    AddAssertionRequest,
    AssertionRecordedResponse,
    AttentionCandidateResult,
    AttentionWorkingSetRequest,
    AttentionWorkingSetResponse,
    CausalEcdRequest,
    CausalEcdResponse,
    ClosurePreview,
    ConceptOption,
    CorrectPropositionRequest,
    CorrectPropositionResponse,
    CreateCausalHypothesisRequest,
    CreateContradictionRequest,
    CreateHypothesisRequest,
    CreateObligationRequest,
    CreateRepairRequest,
    CreateSessionRequest,
    CreateUncertaintyRequest,
    GapWithLabel,
    HumourCheckRequest,
    HumourCheckResponse,
    InterviewAnswerRequest,
    InterviewAnswerResponse,
    InterviewNextResponse,
    InterviewQuestion,
    LoginRequest,
    LoginResponse,
    PromoteHypothesisRequest,
    PromoteHypothesisResponse,
    PsychologicalSafetySignalRequest,
    RegisterRequest,
    ResolveConflictReviewRequest,
    SessionSummary,
    UpdateCausalHypothesisStatusRequest,
    UserPublic,
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


def require_auth(
    authorization: str | None = Header(default=None),
    conn: psycopg.Connection = Depends(get_conn),
) -> User:
    """Gates every endpoint that views session data or takes a clinical/
    Model-Layer action -- see periop_core.auth's module docstring for
    the access-boundary rationale and README for which endpoints this
    is and isn't applied to. Expects `Authorization: Bearer <token>`;
    an invalid, missing or expired token is 401, deliberately with no
    distinction in the error message (never reveal *why* a token
    failed to an unauthenticated caller)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    session = auth_db.get_session(conn, token)
    if session is None or session.is_expired():
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    user = auth_db.get_user_by_id(conn, session.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return user


def _user_public(user: User) -> UserPublic:
    return UserPublic(user_id=user.user_id, username=user.username, created_at=user.created_at)


@app.post("/api/auth/register", response_model=UserPublic, status_code=201)
def register_endpoint(body: RegisterRequest, conn: psycopg.Connection = Depends(get_conn)):
    """Staff/clinician account creation -- see periop_core.auth. Demo
    scope: open registration, no email verification or invite flow (a
    real deployment would gate this behind an admin/invite step rather
    than letting anyone create an account)."""
    if auth_db.get_user_by_username(conn, body.username) is not None:
        raise HTTPException(status_code=409, detail=f"Username {body.username!r} is already taken")
    try:
        password_hash = hash_password(body.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    user = User(username=body.username, password_hash=password_hash)
    auth_db.insert_user(conn, user)
    return _user_public(user)


@app.post("/api/auth/login", response_model=LoginResponse)
def login_endpoint(body: LoginRequest, conn: psycopg.Connection = Depends(get_conn)):
    user = auth_db.get_user_by_username(conn, body.username)
    # Same generic failure whether the username doesn't exist or the
    # password is wrong -- never let a caller enumerate valid usernames.
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    session = new_session(user.user_id)
    auth_db.insert_session(conn, session)
    return LoginResponse(token=session.token, user=_user_public(user), expires_at=session.expires_at)


@app.post("/api/auth/logout", status_code=204)
def logout_endpoint(
    current_user: User = Depends(require_auth),
    authorization: str = Header(),
    conn: psycopg.Connection = Depends(get_conn),
):
    # require_auth already validated this header; re-parsing it here
    # just recovers the raw token to delete (it returns the User, not
    # the token itself).
    token = authorization.removeprefix("Bearer ").strip()
    auth_db.delete_session(conn, token)


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


@app.post("/api/sessions/{session_id}/assertions", response_model=AssertionRecordedResponse)
def add_assertion_endpoint(
    session_id: uuid.UUID,
    body: AddAssertionRequest,
    conn: psycopg.Connection = Depends(get_conn),
):
    """Patient-facing and deliberately unauthenticated (see
    periop_core.auth) -- but that means its response must never leak
    the clinical summary (gaps, conflicts, Model Layer state) the way
    it used to. Still recomputes and persists that state internally
    (so it's ready the moment staff log in and look), just doesn't
    return it here. See AssertionRecordedResponse's docstring."""
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
    _record_assertion(conn, assertion)
    return AssertionRecordedResponse(session_id=session_id, assertion_id=assertion.assertion_id)


def _record_assertion(conn: psycopg.Connection, assertion: Assertion) -> SessionSummary:
    """The single write path for assertions, shared by the manual form and
    the interviewer: insert, audit, then recompute derived state."""
    db.insert_assertion(conn, assertion)
    audit_db.append_event(
        conn,
        AuditEvent(
            session_id=assertion.session_id,
            event_type=AuditEventType.ASSERTION_ADDED,
            entity_type="assertion",
            entity_id=assertion.assertion_id,
            payload={
                "concept_code": assertion.concept.code,
                "assertion_state": assertion.assertion_state.value,
                "source_type": assertion.source.source_type,
                "speaker": assertion.source.speaker.value,
                "entered_via": assertion.provenance.get("entered_via"),
            },
        ),
    )
    return _recompute_and_summarise(conn, assertion.session_id)


# ------------------------------------------------- conversational interview
#
# Patient-facing and unauthenticated, like /assertions above, and bound by
# the same rule: responses carry the next question only, never clinical
# state. The LLM's role is bounded per spec §10.2 -- see
# periop_core.interview_llm.

_INTERVIEW_UNAVAILABLE = "AI interviewer unavailable -- please use the form instead"
_MAX_PATIENT_ATTEMPTS_PER_QUESTION = 2


def _require_active(session: Session) -> None:
    if session.status is not SessionStatus.ACTIVE:
        raise HTTPException(
            status_code=409, detail=f"Interview requires an ACTIVE session (status {session.status})"
        )


def _ask(
    conn: psycopg.Connection,
    action: InterviewAction,
    client,
    modality: Modality,
    *,
    previous_recorded: bool | None,
    reask: bool = False,
) -> InterviewQuestion:
    """Realise the action's question (LLM-003, template fallback) and record
    the delivered agent Turn against it (INV-008)."""
    label = default_concept_labels().get(action.targets[0], {})
    text, _ = realise_question(
        client,
        patient_question=action.fallback or label.get("patient_question", ""),
        concept_label=label.get("concept", action.targets[0]),
        domain=label.get("domain", ""),
        previous_recorded=previous_recorded,
        reask=reask,
    )
    db.insert_turn(conn, Turn(session_id=action.session_id, action_id=action.action_id,
                              speaker=Speaker.AGENT, modality=modality, content=text))
    db.set_interview_action_status(conn, action.action_id, InterviewActionStatus.DELIVERED)
    return InterviewQuestion(action_id=action.action_id, concept_id=action.targets[0],
                             question=text, reask=reask)


def _next_question(
    conn: psycopg.Connection,
    session_id: uuid.UUID,
    gaps: list[GapWithLabel],
    client,
    modality: Modality,
    *,
    previous_recorded: bool | None,
) -> InterviewQuestion | None:
    """Highest-priority open gap not yet asked this session. The
    InterviewAction is persisted before any LLM generation (INV-007)."""
    labels = default_concept_labels()
    asked = db.asked_targets(conn, session_id)
    target = next(
        (g.requirement_id for g in gaps
         if g.requirement_id not in asked and labels.get(g.requirement_id, {}).get("patient_question")),
        None,
    )
    if target is None:
        return None
    label = labels[target]
    action = InterviewAction(
        session_id=session_id,
        action_type=ActionType.CLOSED_SCREEN if label.get("response_type") == "boolean"
        else ActionType.FOCUSED_PROBE,
        targets=[target],
        purpose=f"Ask about: {label.get('concept', target)}",
        permitted_content=[label["patient_question"]],
        prohibited_content=["diagnosis", "medical advice", "reassurance about fitness for surgery",
                            "facts about the patient not in the question"],
        fallback=label["patient_question"],
    )
    db.insert_interview_action(conn, action)
    return _ask(conn, action, client, modality, previous_recorded=previous_recorded)


@app.post("/api/sessions/{session_id}/interview/next", response_model=InterviewNextResponse)
def interview_next_endpoint(
    session_id: uuid.UUID,
    modality: Modality = Modality.TEXT,
    conn: psycopg.Connection = Depends(get_conn),
    client=Depends(get_llm_client),
):
    session = _get_session_or_404(conn, session_id)
    _require_active(session)
    if client is None:
        raise HTTPException(status_code=503, detail=_INTERVIEW_UNAVAILABLE)
    summary = _recompute_and_summarise(conn, session_id)
    question = _next_question(conn, session_id, summary.gaps, client, modality, previous_recorded=None)
    return InterviewNextResponse(done=question is None, next=question)


@app.post("/api/sessions/{session_id}/interview/answer", response_model=InterviewAnswerResponse)
def interview_answer_endpoint(
    session_id: uuid.UUID,
    body: InterviewAnswerRequest,
    conn: psycopg.Connection = Depends(get_conn),
    client=Depends(get_llm_client),
):
    session = _get_session_or_404(conn, session_id)
    _require_active(session)
    try:
        action = db.get_interview_action(conn, body.action_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown interview question") from None
    if action.session_id != session_id:
        raise HTTPException(status_code=404, detail="Unknown interview question")
    turns = db.list_turns(conn, session_id)
    if not turns or turns[-1].speaker is not Speaker.AGENT or turns[-1].action_id != action.action_id:
        raise HTTPException(status_code=409, detail="That is not the question currently being asked")

    patient_turn = Turn(session_id=session_id, action_id=action.action_id, speaker=Speaker.PATIENT,
                        modality=body.modality, content=body.transcript, confidence=body.stt_confidence)
    db.insert_turn(conn, patient_turn)

    concept_id = action.targets[0]
    label = default_concept_labels().get(concept_id, {})
    action_turns = [t for t in turns if t.action_id == action.action_id]
    try:
        candidate = extract_answer(
            client,
            concept_label=label.get("concept", concept_id),
            clinical_definition=label.get("clinical_definition", ""),
            question=action.fallback or label.get("patient_question", ""),
            response_type=label.get("response_type", ""),
            transcript=body.transcript,
            recent_turns=[(t.speaker.value.lower(), t.content) for t in action_turns[:-1]],
        )
    except InterviewerUnavailable:
        raise HTTPException(status_code=503, detail=_INTERVIEW_UNAVAILABLE) from None

    answer = validate_candidate(candidate, concept_id)
    if answer is not None:
        assertion = Assertion(
            session_id=session_id,
            subject_ref=session.subject_ref,
            # TERM-001: the patient's own words are the concept's original text.
            concept=ConceptReference(original_text=body.transcript, code=concept_id),
            value=answer.value,
            assertion_state=answer.assertion_state,
            source=SourceReference(source_type="PATIENT", speaker=Speaker.PATIENT,
                                   turn_id=patient_turn.turn_id),
            certainty=answer.certainty,
            provenance={
                "entered_via": "LLM-001 turn extraction",
                "model": llm_model(),
                "prompt_version": PROMPT_VERSION,
                "turn_id": str(patient_turn.turn_id),
                "action_id": str(action.action_id),
                "modality": body.modality.value,
            },
        )
        summary = _record_assertion(conn, assertion)
        question = _next_question(conn, session_id, summary.gaps, client, body.modality,
                                  previous_recorded=True)
        return InterviewAnswerResponse(recorded=True, done=question is None, next=question)

    patient_attempts = sum(1 for t in action_turns if t.speaker is Speaker.PATIENT) + 1
    if patient_attempts < _MAX_PATIENT_ATTEMPTS_PER_QUESTION:
        question = _ask(conn, action, client, body.modality, previous_recorded=False, reask=True)
        return InterviewAnswerResponse(recorded=False, done=False, next=question)

    # Still unclear after a re-ask: move on and leave the gap open --
    # never fabricate an answer.
    summary = _recompute_and_summarise(conn, session_id)
    question = _next_question(conn, session_id, summary.gaps, client, body.modality,
                              previous_recorded=False)
    return InterviewAnswerResponse(recorded=False, done=question is None, next=question)


@app.get("/api/sessions/{session_id}/summary", response_model=SessionSummary)
def get_summary_endpoint(
    session_id: uuid.UUID,
    conn: psycopg.Connection = Depends(get_conn),
    current_user: User = Depends(require_auth),
):
    _get_session_or_404(conn, session_id)
    return _recompute_and_summarise(conn, session_id)


@app.post("/api/sessions/{session_id}/close", response_model=SessionSummary)
def close_session_endpoint(
    session_id: uuid.UUID,
    conn: psycopg.Connection = Depends(get_conn),
    current_user: User = Depends(require_auth),
):
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
def get_audit_lineage_endpoint(
    session_id: uuid.UUID,
    conn: psycopg.Connection = Depends(get_conn),
    current_user: User = Depends(require_auth),
):
    """SVC-014's `getLineage`. Covers the Phase 1 core lifecycle plus the
    v1.1 Model Layer mutations listed in periop_core.enums.AuditEventType
    -- see README."""
    _get_session_or_404(conn, session_id)
    return audit_db.get_lineage(conn, session_id)


@app.post(
    "/api/sessions/{session_id}/conflict-reviews/{review_id}/resolve",
    response_model=ConflictReview,
)
def resolve_conflict_review_endpoint(
    session_id: uuid.UUID,
    review_id: uuid.UUID,
    body: ResolveConflictReviewRequest,
    conn: psycopg.Connection = Depends(get_conn),
    current_user: User = Depends(require_auth),
):
    """A ConflictReview is logged automatically (see
    _log_new_conflict_reviews) the first time reconciliation detects a
    real patient-vs-record disagreement -- this is how a clinician
    records the decision. RECONCILED means they picked which side is
    correct (`resolved_value` required); ESCALATED means neither side
    is trusted as-is, but who escalated it and why are still required.
    Both are enforced by ConflictReview's own validator, not a
    hand-written check here -- a status transition without a recorded
    decision fails with 422. `resolved_by` is the authenticated
    caller's username, never client-supplied (see
    ResolveConflictReviewRequest's docstring)."""
    _get_session_or_404(conn, session_id)
    if body.status not in (ContradictionStatus.RECONCILED, ContradictionStatus.ESCALATED):
        raise HTTPException(
            status_code=422, detail="status must be RECONCILED or ESCALATED"
        )
    try:
        review = conflict_review_db.get_conflict_review(conn, review_id)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"ConflictReview {review_id} not found"
        ) from None
    if review.status != ContradictionStatus.OPEN:
        raise HTTPException(
            status_code=409,
            detail=f"ConflictReview {review_id} is already {review.status.value}",
        )

    try:
        updated = ConflictReview(
            **{
                **review.model_dump(),
                "status": body.status,
                "resolution": {
                    "resolved_by": current_user.username,
                    "rationale": body.rationale,
                    "resolved_value": body.resolved_value,
                },
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    conflict_review_db.update_conflict_review_resolution(conn, updated)
    audit_db.append_event(
        conn,
        AuditEvent(
            session_id=session_id,
            event_type=AuditEventType.CONFLICT_REVIEW_RESOLVED,
            entity_type="conflict_review",
            entity_id=review_id,
            payload={"status": updated.status.value, "resolved_by": current_user.username},
        ),
    )
    return updated


@app.post("/api/sessions/{session_id}/hypotheses", response_model=ConversationalHypothesis)
def create_hypothesis_endpoint(
    session_id: uuid.UUID,
    body: CreateHypothesisRequest,
    conn: psycopg.Connection = Depends(get_conn),
    current_user: User = Depends(require_auth),
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
    audit_db.append_event(
        conn,
        AuditEvent(
            session_id=session_id,
            event_type=AuditEventType.HYPOTHESIS_CREATED,
            entity_type="hypothesis",
            entity_id=hypothesis.hypothesis_id,
            payload={"content": hypothesis.content, "epistemic_level": hypothesis.epistemic_level.value},
        ),
    )
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
    current_user: User = Depends(require_auth),
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
    audit_db.append_event(
        conn,
        AuditEvent(
            session_id=session_id,
            event_type=AuditEventType.HYPOTHESIS_PROMOTED,
            entity_type="hypothesis",
            entity_id=hypothesis_id,
            payload={"target_level": body.target_level.value, "proposition_id": str(proposition.proposition_id)},
        ),
    )
    return PromoteHypothesisResponse(hypothesis=updated_hypothesis, proposition=proposition)


@app.post(
    "/api/sessions/{session_id}/propositions/{proposition_id}/correct",
    response_model=CorrectPropositionResponse,
)
def correct_proposition_endpoint(
    session_id: uuid.UUID,
    proposition_id: uuid.UUID,
    body: CorrectPropositionRequest,
    conn: psycopg.Connection = Depends(get_conn),
    current_user: User = Depends(require_auth),
):
    """v1.1 §6A.4 ('a repaired fact must propagate through the assertion
    graph and invalidate stale downstream inference') / §6A.15 ('repair
    is mandatory when material misunderstanding is detected'). Replaces
    a GroundedProposition's content, marks the original superseded_by
    the replacement, and -- real exact-match graph traversal, not an
    LLM judgement call, see periop_core.model_layer_gate's docstring --
    finds every hypothesis/proposition/causal hypothesis that cited the
    original as evidence and logs a RepairRequirement for the
    correction. The repair is created even when nothing depended on the
    original: a correction is never silent."""
    _get_session_or_404(conn, session_id)
    try:
        original = model_layer_db.get_grounded_proposition(conn, proposition_id)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Proposition {proposition_id} not found"
        ) from None
    if original.superseded_by is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Proposition {proposition_id} is already superseded by {original.superseded_by}",
        )

    try:
        replacement = GroundedProposition(
            session_id=session_id,
            content=body.content,
            concept=original.concept,
            epistemic_level=original.epistemic_level,
            grounding_evidence=body.grounding_evidence,
            source_assertion_ids=original.source_assertion_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    ref = reference_string("proposition", original.proposition_id)
    dependents = find_dependents(
        ref,
        hypotheses=model_layer_db.list_conversational_hypotheses(conn, session_id),
        propositions=model_layer_db.list_grounded_propositions(conn, session_id),
        causal_hypotheses=model_layer_db.list_causal_hypotheses(conn, session_id),
    )
    repair = required_repair_for_correction(ref, dependents, session_id=session_id)

    model_layer_db.insert_grounded_proposition(conn, replacement)
    model_layer_db.update_grounded_proposition_superseded(
        conn, original.proposition_id, replacement.proposition_id
    )
    model_layer_db.insert_repair_requirement(conn, repair)
    audit_db.append_event(
        conn,
        AuditEvent(
            session_id=session_id,
            event_type=AuditEventType.PROPOSITION_CORRECTED,
            entity_type="proposition",
            entity_id=proposition_id,
            payload={
                "replacement_id": str(replacement.proposition_id),
                "repair_id": str(repair.repair_id),
                "dependents_found": dependents.total_count(),
            },
        ),
    )

    updated_original = original.model_copy(update={"superseded_by": replacement.proposition_id})
    return CorrectPropositionResponse(
        original=updated_original,
        replacement=replacement,
        repair=repair,
        dependents_found=dependents.total_count(),
    )


@app.post("/api/sessions/{session_id}/obligations", response_model=ProspectiveObligation)
def create_obligation_endpoint(
    session_id: uuid.UUID,
    body: CreateObligationRequest,
    conn: psycopg.Connection = Depends(get_conn),
    current_user: User = Depends(require_auth),
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
    audit_db.append_event(
        conn,
        AuditEvent(
            session_id=session_id,
            event_type=AuditEventType.OBLIGATION_CREATED,
            entity_type="obligation",
            entity_id=obligation.obligation_id,
            payload={"content": obligation.content, "source": obligation.source},
        ),
    )
    return obligation


@app.post("/api/sessions/{session_id}/contradictions", response_model=Contradiction)
def create_contradiction_endpoint(
    session_id: uuid.UUID,
    body: CreateContradictionRequest,
    conn: psycopg.Connection = Depends(get_conn),
    current_user: User = Depends(require_auth),
):
    """Table 9 -- a conversation-level incompatibility, distinct from a
    Clinical State Conflict. **Not implemented**: promoting a
    Contradiction into a formal `periop_core.models.Conflict`
    (`promoted_conflict_id`) -- see periop_core.model_layer's module
    docstring; WorkingFact/Conflict are recomputed wholesale each
    reconciliation pass (periop_core.db), so a standalone Conflict
    inserted here would be silently wiped out by the next assertion,
    which would be a real correctness bug, not a documented
    simplification. This endpoint only logs the Contradiction itself."""
    _get_session_or_404(conn, session_id)
    try:
        contradiction = Contradiction(
            session_id=session_id,
            description=body.description,
            involved_ids=body.involved_ids,
            status=body.status,
        )
    except ValueError as exc:
        # e.g. fewer than two involved_ids (Table 9 invariant).
        raise HTTPException(status_code=422, detail=str(exc)) from None
    model_layer_db.insert_contradiction(conn, contradiction)
    audit_db.append_event(
        conn,
        AuditEvent(
            session_id=session_id,
            event_type=AuditEventType.CONTRADICTION_LOGGED,
            entity_type="contradiction",
            entity_id=contradiction.contradiction_id,
            payload={"description": contradiction.description, "involved_ids": [str(i) for i in contradiction.involved_ids]},
        ),
    )
    return contradiction


@app.post("/api/sessions/{session_id}/uncertainties", response_model=Uncertainty)
def create_uncertainty_endpoint(
    session_id: uuid.UUID,
    body: CreateUncertaintyRequest,
    conn: psycopg.Connection = Depends(get_conn),
    current_user: User = Depends(require_auth),
):
    """Table 9 -- an explicit unresolved ambiguity/missing-value/
    uncertain interpretation, deliberately distinct from a negative
    finding. See periop_core.model_layer.Uncertainty's docstring."""
    _get_session_or_404(conn, session_id)
    concept = None
    if body.concept_code:
        labels = default_concept_labels()
        concept_label = labels.get(body.concept_code, {}).get("concept", body.concept_code)
        concept = ConceptReference(
            original_text=body.concept_text or concept_label, code=body.concept_code
        )
    uncertainty = Uncertainty(
        session_id=session_id,
        concept=concept,
        description=body.description,
        kind=body.kind,
    )
    model_layer_db.insert_uncertainty(conn, uncertainty)
    audit_db.append_event(
        conn,
        AuditEvent(
            session_id=session_id,
            event_type=AuditEventType.UNCERTAINTY_LOGGED,
            entity_type="uncertainty",
            entity_id=uncertainty.uncertainty_id,
            payload={"description": uncertainty.description, "kind": uncertainty.kind},
        ),
    )
    return uncertainty


@app.post("/api/sessions/{session_id}/causal-hypotheses", response_model=CausalHypothesis)
def create_causal_hypothesis_endpoint(
    session_id: uuid.UUID,
    body: CreateCausalHypothesisRequest,
    conn: psycopg.Connection = Depends(get_conn),
    current_user: User = Depends(require_auth),
):
    """Table 9 / 6A.10 -- a provisional cause-effect explanation. Kept
    distinct from the standalone causal-ECD calculator
    (POST /api/tools/causal-ecd): this persists an actual session-scoped
    CausalHypothesis row; the calculator is just Shannon-entropy maths
    over a prior/likelihoods the caller supplies."""
    _get_session_or_404(conn, session_id)
    try:
        causal = CausalHypothesis(
            session_id=session_id,
            cause=body.cause,
            effect=body.effect,
            supporting_evidence=body.supporting_evidence,
            alternatives=body.alternatives,
            confidence=body.confidence,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    model_layer_db.insert_causal_hypothesis(conn, causal)
    audit_db.append_event(
        conn,
        AuditEvent(
            session_id=session_id,
            event_type=AuditEventType.CAUSAL_HYPOTHESIS_CREATED,
            entity_type="causal_hypothesis",
            entity_id=causal.causal_id,
            payload={"cause": causal.cause, "effect": causal.effect, "confidence": causal.confidence},
        ),
    )
    return causal


@app.post(
    "/api/sessions/{session_id}/causal-hypotheses/{causal_id}/status",
    response_model=CausalHypothesis,
)
def update_causal_hypothesis_status_endpoint(
    session_id: uuid.UUID,
    causal_id: uuid.UUID,
    body: UpdateCausalHypothesisStatusRequest,
    conn: psycopg.Connection = Depends(get_conn),
    current_user: User = Depends(require_auth),
):
    """6A.10 -- moves a CausalHypothesis along CausalRelationStatus (e.g.
    DISCRIMINATED once a discriminating question has been asked, or
    ADJUDICATED once a clinician has reached a judgement). Reaching
    ADJUDICATED without `adjudicated_by` fails with 422 -- the object's
    own validator, not a hand-written check here: 'causal hypotheses do
    not become authoritative causal assertions without clinician
    adjudication'."""
    _get_session_or_404(conn, session_id)
    try:
        causal = model_layer_db.get_causal_hypothesis(conn, causal_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"CausalHypothesis {causal_id} not found") from None

    try:
        updated = CausalHypothesis(
            **{
                **causal.model_dump(),
                "status": body.status,
                "adjudicated_by": body.adjudicated_by,
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    model_layer_db.update_causal_hypothesis_status(conn, updated)
    audit_db.append_event(
        conn,
        AuditEvent(
            session_id=session_id,
            event_type=AuditEventType.CAUSAL_HYPOTHESIS_STATUS_CHANGED,
            entity_type="causal_hypothesis",
            entity_id=causal_id,
            payload={"status": updated.status.value, "adjudicated_by": updated.adjudicated_by},
        ),
    )
    return updated


@app.post("/api/sessions/{session_id}/repairs", response_model=RepairRequirement)
def create_repair_endpoint(
    session_id: uuid.UUID,
    body: CreateRepairRequest,
    conn: psycopg.Connection = Depends(get_conn),
    current_user: User = Depends(require_auth),
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
    audit_db.append_event(
        conn,
        AuditEvent(
            session_id=session_id,
            event_type=AuditEventType.REPAIR_CREATED,
            entity_type="repair",
            entity_id=repair.repair_id,
            payload={"repair_type": repair.repair_type.value, "materiality": repair.materiality.value},
        ),
    )
    return repair


@app.post("/api/sessions/{session_id}/repairs/{repair_id}/resolve", response_model=RepairRequirement)
def resolve_repair_endpoint(
    session_id: uuid.UUID,
    repair_id: uuid.UUID,
    conn: psycopg.Connection = Depends(get_conn),
    current_user: User = Depends(require_auth),
):
    _get_session_or_404(conn, session_id)
    try:
        repair = model_layer_db.get_repair_requirement(conn, repair_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Repair {repair_id} not found") from None

    resolved = repair.model_copy(update={"status": RepairStatus.REPAIRED})
    model_layer_db.update_repair_requirement(conn, resolved)
    audit_db.append_event(
        conn,
        AuditEvent(
            session_id=session_id,
            event_type=AuditEventType.REPAIR_RESOLVED,
            entity_type="repair",
            entity_id=repair_id,
            payload={},
        ),
    )
    return resolved


@app.post(
    "/api/sessions/{session_id}/psychological-safety/signal",
    response_model=PsychologicalSafetyState,
)
def apply_psychological_safety_signal_endpoint(
    session_id: uuid.UUID,
    body: PsychologicalSafetySignalRequest,
    conn: psycopg.Connection = Depends(get_conn),
    current_user: User = Depends(require_auth),
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
    audit_db.append_event(
        conn,
        AuditEvent(
            session_id=session_id,
            event_type=AuditEventType.PSYCHOLOGICAL_SAFETY_SIGNAL_APPLIED,
            entity_type="psychological_safety",
            entity_id=session_id,
            payload={"signal_names": body.signal_names, "estimate": updated.estimate},
        ),
    )
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


@app.post("/api/tools/attention-working-set", response_model=AttentionWorkingSetResponse)
def attention_working_set_endpoint(body: AttentionWorkingSetRequest):
    """v1.1 §6A.5 -- a standalone calculator over the real deterministic
    scoring in periop_core.attention, not tied to any session's stored
    objects. Deliberately NOT derived from real hypotheses/propositions/
    obligations: that would mean inventing a risk/clinical-value scoring
    function the spec doesn't define for arbitrary conversational
    objects (the same kind of judgement call reconciliation's
    fitness-based tie-breaking was declined for -- see README).
    Useful for exploring how the weighted-sum ranking and the
    risk-based forced-inclusion rule (6A.5: 'high-risk unresolved
    obligations remain persistent until resolved or handed off') behave
    on a caller-supplied candidate set."""
    if body.max_size < 0:
        raise HTTPException(status_code=422, detail="max_size must be >= 0")
    try:
        candidates = [
            AttentionCandidate(item=c.label, factors=AttentionFactors(**c.factors.model_dump()))
            for c in body.candidates
        ]
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    result = select_working_set(candidates, max_size=body.max_size)
    ranked = sorted(
        ((c, result.scores[id(c.item)]) for c in candidates),
        key=lambda pair: pair[1],
        reverse=True,
    )
    return AttentionWorkingSetResponse(
        working_set=result.working_set,
        forced_inclusions=result.forced_inclusions,
        candidates=[
            AttentionCandidateResult(
                label=c.item,
                score=score,
                in_working_set=c.item in result.working_set,
                forced_inclusion=c.item in result.forced_inclusions,
            )
            for c, score in ranked
        ],
    )


def _get_session_or_404(conn: psycopg.Connection, session_id: uuid.UUID) -> Session:
    try:
        return db.get_session(conn, session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found") from None


# Fixed namespace for deterministic ConflictReview ids -- see
# _conflict_review_id below and ConflictReview's docstring on why the id
# must be stable across recomputes rather than minted fresh each time.
_CONFLICT_REVIEW_NAMESPACE = uuid.UUID("5b6e4f0a-5e8b-4f1a-9b3a-4c7b1f6d2a10")


def _conflict_review_id(session_id: uuid.UUID, assertion_ids: list[uuid.UUID]) -> uuid.UUID:
    key = str(session_id) + ":" + ",".join(sorted(str(a) for a in assertion_ids))
    return uuid.uuid5(_CONFLICT_REVIEW_NAMESPACE, key)


def _log_new_conflict_reviews(
    conn: psycopg.Connection,
    session_id: uuid.UUID,
    conflicts: list,
    assertions: list[Assertion],
) -> None:
    """For every Conflict this reconciliation pass produced, log a durable
    ConflictReview the first time this exact disagreeing-assertion-set is
    seen -- never touching one that already exists, so a clinician's
    resolution is never overwritten by the next recompute. See
    ConflictReview's docstring for why this can't just be a field on
    Conflict itself."""
    assertions_by_id = {a.assertion_id: a for a in assertions}
    for conflict in conflicts:
        review_id = _conflict_review_id(session_id, conflict.assertion_ids)
        try:
            conflict_review_db.get_conflict_review(conn, review_id)
            continue
        except KeyError:
            pass

        sides = []
        concept = None
        for assertion_id in conflict.assertion_ids:
            assertion = assertions_by_id.get(assertion_id)
            if assertion is None:
                continue
            concept = concept or assertion.concept
            sides.append(
                ConflictReviewSide(
                    assertion_id=assertion.assertion_id,
                    source_type=assertion.source.source_type,
                    speaker=assertion.source.speaker,
                    value=assertion.value,
                    original_text=assertion.concept.original_text,
                    recorded_at=assertion.assertion_time,
                )
            )
        if concept is None or len(sides) < 2:
            continue

        review = ConflictReview(
            review_id=review_id,
            session_id=session_id,
            conflict_id=conflict.conflict_id,
            concept=concept,
            sides=sides,
        )
        conflict_review_db.insert_conflict_review(conn, review)
        audit_db.append_event(
            conn,
            AuditEvent(
                session_id=session_id,
                event_type=AuditEventType.CONFLICT_REVIEW_CREATED,
                entity_type="conflict_review",
                entity_id=review.review_id,
                payload={"concept_code": concept.code, "sides": len(sides)},
            ),
        )


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
    _log_new_conflict_reviews(conn, session_id, conflicts, assertions)

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
    contradictions = model_layer_db.list_contradictions(conn, session_id)
    uncertainties = model_layer_db.list_uncertainties(conn, session_id)
    causal_hypotheses = model_layer_db.list_causal_hypotheses(conn, session_id)
    psychological_safety = model_layer_db.get_psychological_safety_state(conn, session_id)
    conflict_reviews = conflict_review_db.list_conflict_reviews(conn, session_id)

    closure = evaluate_closure(
        open_tasks=tasks,
        agenda_items=agenda_items,
        conflicts=conflicts,
        repair_requirements=repairs,
        conflict_reviews=conflict_reviews,
    )

    return SessionSummary(
        session=session,
        working_facts=facts,
        conflicts=conflicts,
        conflict_reviews=conflict_reviews,
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
        contradictions=contradictions,
        uncertainties=uncertainties,
        causal_hypotheses=causal_hypotheses,
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
