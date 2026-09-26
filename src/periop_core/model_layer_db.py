"""Persistence for the v1.1 Model Layer objects (periop_core.model_layer),
against db/migrations/0002_model_layer.sql. Follows the same patterns as
periop_core.db (kept as a separate module purely to keep file size
manageable -- these are conceptually the same kind of repository code).

Scope honestly stated: unlike WorkingFact/RequirementState/InformationGap
in periop_core.db, these objects are treated as an append-only list per
session (insert once, list all) with targeted updates only where the
object model itself mutates a field in place (a hypothesis's status
after promotion; a repair's status when resolved). There is no
delete-and-recompute pass here because nothing yet *recomputes* Model
Layer state the way reconciliation recomputes WorkingFacts -- that would
be Orchestrator-side logic that doesn't exist yet.
"""
from __future__ import annotations

import uuid

import psycopg
from psycopg.types.json import Jsonb

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


# ------------------------------------------------------------ propositions

def insert_grounded_proposition(conn: psycopg.Connection, prop: GroundedProposition) -> None:
    conn.execute(
        """
        INSERT INTO grounded_proposition
            (proposition_id, session_id, content, concept_json, epistemic_level,
             grounding_evidence_json, source_assertion_ids_json, established_at, superseded_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            prop.proposition_id,
            prop.session_id,
            prop.content,
            Jsonb(prop.concept.model_dump(mode="json")) if prop.concept else None,
            prop.epistemic_level.value,
            Jsonb(prop.grounding_evidence),
            Jsonb([str(i) for i in prop.source_assertion_ids]),
            prop.established_at,
            prop.superseded_by,
        ),
    )


def _row_to_grounded_proposition(row) -> GroundedProposition:
    from periop_core.models import ConceptReference

    return GroundedProposition(
        proposition_id=row[0],
        session_id=row[1],
        content=row[2],
        concept=ConceptReference.model_validate(row[3]) if row[3] else None,
        epistemic_level=row[4],
        grounding_evidence=row[5],
        source_assertion_ids=row[6],
        established_at=row[7],
        superseded_by=row[8],
    )


def list_grounded_propositions(
    conn: psycopg.Connection, session_id: uuid.UUID
) -> list[GroundedProposition]:
    rows = conn.execute(
        """
        SELECT proposition_id, session_id, content, concept_json, epistemic_level,
               grounding_evidence_json, source_assertion_ids_json, established_at, superseded_by
        FROM grounded_proposition WHERE session_id = %s ORDER BY established_at
        """,
        (session_id,),
    ).fetchall()
    return [_row_to_grounded_proposition(r) for r in rows]


# ------------------------------------------------------------ hypotheses

def insert_conversational_hypothesis(
    conn: psycopg.Connection, hyp: ConversationalHypothesis
) -> None:
    conn.execute(
        """
        INSERT INTO conversational_hypothesis
            (hypothesis_id, session_id, content, epistemic_level, status,
             supporting_observations_json, confidence, promoted_proposition_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            hyp.hypothesis_id,
            hyp.session_id,
            hyp.content,
            hyp.epistemic_level.value,
            hyp.status.value,
            Jsonb(hyp.supporting_observations),
            hyp.confidence,
            hyp.promoted_proposition_id,
        ),
    )


def update_conversational_hypothesis(
    conn: psycopg.Connection, hyp: ConversationalHypothesis
) -> None:
    conn.execute(
        """
        UPDATE conversational_hypothesis
        SET status = %s, promoted_proposition_id = %s
        WHERE hypothesis_id = %s
        """,
        (hyp.status.value, hyp.promoted_proposition_id, hyp.hypothesis_id),
    )


def _row_to_hypothesis(row) -> ConversationalHypothesis:
    return ConversationalHypothesis(
        hypothesis_id=row[0],
        session_id=row[1],
        content=row[2],
        epistemic_level=row[3],
        status=row[4],
        supporting_observations=row[5],
        confidence=float(row[6]) if row[6] is not None else None,
        promoted_proposition_id=row[7],
    )


def list_conversational_hypotheses(
    conn: psycopg.Connection, session_id: uuid.UUID
) -> list[ConversationalHypothesis]:
    rows = conn.execute(
        """
        SELECT hypothesis_id, session_id, content, epistemic_level, status,
               supporting_observations_json, confidence, promoted_proposition_id
        FROM conversational_hypothesis WHERE session_id = %s
        """,
        (session_id,),
    ).fetchall()
    return [_row_to_hypothesis(r) for r in rows]


def get_conversational_hypothesis(
    conn: psycopg.Connection, hypothesis_id: uuid.UUID
) -> ConversationalHypothesis:
    row = conn.execute(
        """
        SELECT hypothesis_id, session_id, content, epistemic_level, status,
               supporting_observations_json, confidence, promoted_proposition_id
        FROM conversational_hypothesis WHERE hypothesis_id = %s
        """,
        (hypothesis_id,),
    ).fetchone()
    if row is None:
        raise KeyError(f"ConversationalHypothesis {hypothesis_id} not found")
    return _row_to_hypothesis(row)


# ------------------------------------------------------------ obligations

def insert_prospective_obligation(
    conn: psycopg.Connection, obligation: ProspectiveObligation
) -> None:
    conn.execute(
        """
        INSERT INTO prospective_obligation
            (obligation_id, session_id, content, source, priority, risk, trigger,
             deadline, status, resulting_task_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            obligation.obligation_id,
            obligation.session_id,
            obligation.content,
            obligation.source,
            obligation.priority.value,
            obligation.risk.value,
            obligation.trigger,
            obligation.deadline,
            obligation.status.value,
            obligation.resulting_task_id,
        ),
    )


def _row_to_obligation(row) -> ProspectiveObligation:
    return ProspectiveObligation(
        obligation_id=row[0],
        session_id=row[1],
        content=row[2],
        source=row[3],
        priority=row[4],
        risk=row[5],
        trigger=row[6],
        deadline=row[7],
        status=row[8],
        resulting_task_id=row[9],
    )


def list_prospective_obligations(
    conn: psycopg.Connection, session_id: uuid.UUID
) -> list[ProspectiveObligation]:
    rows = conn.execute(
        """
        SELECT obligation_id, session_id, content, source, priority, risk, trigger,
               deadline, status, resulting_task_id
        FROM prospective_obligation WHERE session_id = %s
        """,
        (session_id,),
    ).fetchall()
    return [_row_to_obligation(r) for r in rows]


# ------------------------------------------------------------- repairs

def insert_repair_requirement(conn: psycopg.Connection, repair: RepairRequirement) -> None:
    conn.execute(
        """
        INSERT INTO repair_requirement
            (repair_id, session_id, turn_id, repair_type, description, materiality,
             status, ai_self_repair, deferred_reason, obligation_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            repair.repair_id,
            repair.session_id,
            repair.turn_id,
            repair.repair_type.value,
            repair.description,
            repair.materiality.value,
            repair.status.value,
            repair.ai_self_repair,
            repair.deferred_reason,
            repair.obligation_id,
        ),
    )


def update_repair_requirement(conn: psycopg.Connection, repair: RepairRequirement) -> None:
    conn.execute(
        """
        UPDATE repair_requirement
        SET status = %s, deferred_reason = %s, obligation_id = %s
        WHERE repair_id = %s
        """,
        (repair.status.value, repair.deferred_reason, repair.obligation_id, repair.repair_id),
    )


def _row_to_repair(row) -> RepairRequirement:
    return RepairRequirement(
        repair_id=row[0],
        session_id=row[1],
        turn_id=row[2],
        repair_type=row[3],
        description=row[4],
        materiality=row[5],
        status=row[6],
        ai_self_repair=row[7],
        deferred_reason=row[8],
        obligation_id=row[9],
    )


def list_repair_requirements(
    conn: psycopg.Connection, session_id: uuid.UUID
) -> list[RepairRequirement]:
    rows = conn.execute(
        """
        SELECT repair_id, session_id, turn_id, repair_type, description, materiality,
               status, ai_self_repair, deferred_reason, obligation_id
        FROM repair_requirement WHERE session_id = %s
        """,
        (session_id,),
    ).fetchall()
    return [_row_to_repair(r) for r in rows]


def get_repair_requirement(conn: psycopg.Connection, repair_id: uuid.UUID) -> RepairRequirement:
    row = conn.execute(
        """
        SELECT repair_id, session_id, turn_id, repair_type, description, materiality,
               status, ai_self_repair, deferred_reason, obligation_id
        FROM repair_requirement WHERE repair_id = %s
        """,
        (repair_id,),
    ).fetchone()
    if row is None:
        raise KeyError(f"RepairRequirement {repair_id} not found")
    return _row_to_repair(row)


# --------------------------------------------------------- contradictions

def insert_contradiction(conn: psycopg.Connection, contradiction: Contradiction) -> None:
    conn.execute(
        """
        INSERT INTO contradiction
            (contradiction_id, session_id, description, involved_ids_json, status,
             promoted_conflict_id)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            contradiction.contradiction_id,
            contradiction.session_id,
            contradiction.description,
            Jsonb([str(i) for i in contradiction.involved_ids]),
            contradiction.status.value,
            contradiction.promoted_conflict_id,
        ),
    )


def list_contradictions(conn: psycopg.Connection, session_id: uuid.UUID) -> list[Contradiction]:
    rows = conn.execute(
        """
        SELECT contradiction_id, session_id, description, involved_ids_json, status,
               promoted_conflict_id
        FROM contradiction WHERE session_id = %s
        """,
        (session_id,),
    ).fetchall()
    return [
        Contradiction(
            contradiction_id=r[0],
            session_id=r[1],
            description=r[2],
            involved_ids=r[3],
            status=r[4],
            promoted_conflict_id=r[5],
        )
        for r in rows
    ]


# ----------------------------------------------------------- uncertainty

def insert_uncertainty(conn: psycopg.Connection, uncertainty: Uncertainty) -> None:
    conn.execute(
        """
        INSERT INTO uncertainty (uncertainty_id, session_id, concept_json, description, kind, resolved)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            uncertainty.uncertainty_id,
            uncertainty.session_id,
            Jsonb(uncertainty.concept.model_dump(mode="json")) if uncertainty.concept else None,
            uncertainty.description,
            uncertainty.kind,
            uncertainty.resolved,
        ),
    )


def list_uncertainties(conn: psycopg.Connection, session_id: uuid.UUID) -> list[Uncertainty]:
    from periop_core.models import ConceptReference

    rows = conn.execute(
        """
        SELECT uncertainty_id, session_id, concept_json, description, kind, resolved
        FROM uncertainty WHERE session_id = %s
        """,
        (session_id,),
    ).fetchall()
    return [
        Uncertainty(
            uncertainty_id=r[0],
            session_id=r[1],
            concept=ConceptReference.model_validate(r[2]) if r[2] else None,
            description=r[3],
            kind=r[4],
            resolved=r[5],
        )
        for r in rows
    ]


# ------------------------------------------------------- causal hypotheses

def insert_causal_hypothesis(conn: psycopg.Connection, causal: CausalHypothesis) -> None:
    conn.execute(
        """
        INSERT INTO causal_hypothesis
            (causal_id, session_id, cause, effect, supporting_evidence_json,
             alternatives_json, confidence, status, adjudicated_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            causal.causal_id,
            causal.session_id,
            causal.cause,
            causal.effect,
            Jsonb(causal.supporting_evidence),
            Jsonb(causal.alternatives),
            causal.confidence,
            causal.status.value,
            causal.adjudicated_by,
        ),
    )


def list_causal_hypotheses(conn: psycopg.Connection, session_id: uuid.UUID) -> list[CausalHypothesis]:
    rows = conn.execute(
        """
        SELECT causal_id, session_id, cause, effect, supporting_evidence_json,
               alternatives_json, confidence, status, adjudicated_by
        FROM causal_hypothesis WHERE session_id = %s
        """,
        (session_id,),
    ).fetchall()
    return [
        CausalHypothesis(
            causal_id=r[0],
            session_id=r[1],
            cause=r[2],
            effect=r[3],
            supporting_evidence=r[4],
            alternatives=r[5],
            confidence=float(r[6]),
            status=r[7],
            adjudicated_by=r[8],
        )
        for r in rows
    ]


# ----------------------------------------------------- psychological safety

def upsert_psychological_safety_state(
    conn: psycopg.Connection, state: PsychologicalSafetyState
) -> None:
    conn.execute(
        """
        INSERT INTO psychological_safety_state (session_id, estimate, evidence_signals_json, updated_at)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (session_id) DO UPDATE
        SET estimate = EXCLUDED.estimate,
            evidence_signals_json = EXCLUDED.evidence_signals_json,
            updated_at = EXCLUDED.updated_at
        """,
        (state.session_id, state.estimate, Jsonb(state.evidence_signals), state.updated_at),
    )


def get_psychological_safety_state(
    conn: psycopg.Connection, session_id: uuid.UUID
) -> PsychologicalSafetyState | None:
    row = conn.execute(
        """
        SELECT session_id, estimate, evidence_signals_json, updated_at
        FROM psychological_safety_state WHERE session_id = %s
        """,
        (session_id,),
    ).fetchone()
    if row is None:
        return None
    return PsychologicalSafetyState(
        session_id=row[0], estimate=float(row[1]), evidence_signals=row[2], updated_at=row[3]
    )
