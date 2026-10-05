"""Persistence repository wiring canonical models (periop_core.models) to
the Postgres schema in db/migrations/0001_init.sql.

Scope honestly stated: this is enough persistence for the demo API
(periop_api) to store and retrieve session state across HTTP requests. It
does NOT implement:
- an append-only audit/event log (SVC-014) -- writes here are plain
  inserts/replacements, not event-sourced history;
- optimistic concurrency / per-session serialised mutation (NFR-003) --
  concurrent requests against the same session can race;
- reconstructing SUPPORTS/DISSENTS role distinctions on read (the role is
  written to fact_assertion_link but `list_working_facts` currently
  returns all linked assertion IDs as supporting -- a documented
  simplification, not a silent one).

WorkingFact, RequirementState and InformationGap are treated as fully
*recomputed* derived state: each reconciliation/gap-evaluation pass
deletes and re-inserts the session's rows rather than versioning them.
That matches the model (Assertion is the append-only source of truth;
these are derived from it) but does mean only the *current* pass is
queryable from the DB -- not a history of previous derivations.

Functions take a `psycopg.Connection` explicitly rather than owning a
connection pool, so callers (periop_api) control transaction/connection
lifecycle.
"""
from __future__ import annotations

import uuid
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from periop_core.enums import FactAssertionRole, InterviewActionStatus
from periop_core.models import (
    Assertion,
    ConceptReference,
    Conflict,
    InformationGap,
    InterviewAction,
    OpenTask,
    PatientAgendaItem,
    ReleaseManifest,
    RequirementState,
    Session,
    SourceReference,
    Turn,
    WorkingFact,
)

# ---------------------------------------------------------------- manifest

def insert_release_manifest(conn: psycopg.Connection, manifest: ReleaseManifest) -> None:
    conn.execute(
        """
        INSERT INTO release_manifest (manifest_id, manifest_json, created_at)
        VALUES (%s, %s, %s)
        """,
        (manifest.manifest_id, Jsonb(manifest.model_dump(mode="json")), manifest.created_at),
    )


def get_release_manifest(conn: psycopg.Connection, manifest_id: uuid.UUID) -> ReleaseManifest:
    row = conn.execute(
        "SELECT manifest_json FROM release_manifest WHERE manifest_id = %s", (manifest_id,)
    ).fetchone()
    if row is None:
        raise KeyError(f"ReleaseManifest {manifest_id} not found")
    return ReleaseManifest.model_validate(row[0])


# ----------------------------------------------------------------- session

def insert_session(conn: psycopg.Connection, session: Session) -> None:
    conn.execute(
        """
        INSERT INTO session
            (session_id, subject_ref, encounter_ref, procedure_context_json,
             status, manifest_id, created_at, notice_acknowledged_at, eligibility_result)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            session.session_id,
            session.subject_ref,
            session.encounter_ref,
            Jsonb(session.procedure_context),
            session.status.value,
            session.manifest_id,
            session.created_at,
            session.notice_acknowledged_at,
            session.eligibility_result.value if session.eligibility_result else None,
        ),
    )


def update_session(conn: psycopg.Connection, session: Session) -> None:
    conn.execute(
        """
        UPDATE session
        SET status = %s, notice_acknowledged_at = %s, eligibility_result = %s
        WHERE session_id = %s
        """,
        (
            session.status.value,
            session.notice_acknowledged_at,
            session.eligibility_result.value if session.eligibility_result else None,
            session.session_id,
        ),
    )


def get_session(conn: psycopg.Connection, session_id: uuid.UUID) -> Session:
    row = conn.execute(
        """
        SELECT session_id, subject_ref, encounter_ref, procedure_context_json,
               status, manifest_id, created_at, notice_acknowledged_at, eligibility_result
        FROM session WHERE session_id = %s
        """,
        (session_id,),
    ).fetchone()
    if row is None:
        raise KeyError(f"Session {session_id} not found")
    return Session(
        session_id=row[0],
        subject_ref=row[1],
        encounter_ref=row[2],
        procedure_context=row[3],
        status=row[4],
        manifest_id=row[5],
        created_at=row[6],
        notice_acknowledged_at=row[7],
        eligibility_result=row[8],
    )


# --------------------------------------------------------------- assertion

def insert_assertion(conn: psycopg.Connection, assertion: Assertion) -> None:
    conn.execute(
        """
        INSERT INTO assertion
            (assertion_id, session_id, subject_ref, concept_json, value_json,
             assertion_state, source_json, event_time_json, assertion_time,
             certainty, provenance_json, supersedes_assertion_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            assertion.assertion_id,
            assertion.session_id,
            assertion.subject_ref,
            Jsonb(assertion.concept.model_dump(mode="json")),
            Jsonb(assertion.value) if assertion.value is not None else None,
            assertion.assertion_state.value,
            Jsonb(assertion.source.model_dump(mode="json")),
            Jsonb(assertion.event_time) if assertion.event_time is not None else None,
            assertion.assertion_time,
            assertion.certainty.value,
            Jsonb(assertion.provenance),
            assertion.supersedes_assertion_id,
        ),
    )


def _row_to_assertion(row: tuple[Any, ...]) -> Assertion:
    return Assertion(
        assertion_id=row[0],
        session_id=row[1],
        subject_ref=row[2],
        concept=ConceptReference.model_validate(row[3]),
        value=row[4],
        assertion_state=row[5],
        source=SourceReference.model_validate(row[6]),
        event_time=row[7],
        assertion_time=row[8],
        certainty=row[9],
        provenance=row[10],
        supersedes_assertion_id=row[11],
    )


def list_assertions(conn: psycopg.Connection, session_id: uuid.UUID) -> list[Assertion]:
    rows = conn.execute(
        """
        SELECT assertion_id, session_id, subject_ref, concept_json, value_json,
               assertion_state, source_json, event_time_json, assertion_time,
               certainty, provenance_json, supersedes_assertion_id
        FROM assertion WHERE session_id = %s ORDER BY assertion_time
        """,
        (session_id,),
    ).fetchall()
    return [_row_to_assertion(r) for r in rows]


# ------------------------------------------------- working facts + conflicts

def replace_reconciliation_state(
    conn: psycopg.Connection,
    session_id: uuid.UUID,
    facts: list[WorkingFact],
    conflicts: list[Conflict],
) -> None:
    """Delete-then-reinsert: see module docstring on why facts/conflicts
    are treated as fully recomputed derived state in this demo."""
    conn.execute(
        "DELETE FROM fact_assertion_link WHERE fact_id IN "
        "(SELECT fact_id FROM working_fact WHERE session_id = %s)",
        (session_id,),
    )
    conn.execute("DELETE FROM working_fact WHERE session_id = %s", (session_id,))
    conn.execute(
        "DELETE FROM conflict_assertion_link WHERE conflict_id IN "
        "(SELECT conflict_id FROM conflict WHERE session_id = %s)",
        (session_id,),
    )
    conn.execute("DELETE FROM conflict WHERE session_id = %s", (session_id,))

    for fact in facts:
        conn.execute(
            """
            INSERT INTO working_fact
                (fact_id, session_id, concept_json, value_json, verification_state,
                 freshness_json, version)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                fact.fact_id,
                fact.session_id,
                Jsonb(fact.concept.model_dump(mode="json")),
                Jsonb(fact.value) if fact.value is not None else None,
                fact.verification_state.value,
                Jsonb(fact.freshness) if fact.freshness is not None else None,
                fact.version,
            ),
        )
        for assertion_id in fact.supporting_assertion_ids:
            conn.execute(
                "INSERT INTO fact_assertion_link (fact_id, assertion_id, role) "
                "VALUES (%s, %s, %s)",
                (fact.fact_id, assertion_id, FactAssertionRole.SUPPORTS.value),
            )
        for assertion_id in fact.dissenting_assertion_ids:
            conn.execute(
                "INSERT INTO fact_assertion_link (fact_id, assertion_id, role) "
                "VALUES (%s, %s, %s)",
                (fact.fact_id, assertion_id, FactAssertionRole.DISSENTS.value),
            )

    for conflict in conflicts:
        conn.execute(
            """
            INSERT INTO conflict (conflict_id, session_id, type, materiality, status, resolution_json)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                conflict.conflict_id,
                conflict.session_id,
                conflict.type.value,
                conflict.materiality.value,
                conflict.status.value,
                Jsonb(conflict.resolution) if conflict.resolution is not None else None,
            ),
        )
        for assertion_id in conflict.assertion_ids:
            conn.execute(
                "INSERT INTO conflict_assertion_link (conflict_id, assertion_id) VALUES (%s, %s)",
                (conflict.conflict_id, assertion_id),
            )


def list_working_facts(conn: psycopg.Connection, session_id: uuid.UUID) -> list[WorkingFact]:
    rows = conn.execute(
        """
        SELECT fact_id, session_id, concept_json, value_json, verification_state,
               freshness_json, version
        FROM working_fact WHERE session_id = %s
        """,
        (session_id,),
    ).fetchall()
    facts = []
    for row in rows:
        links = conn.execute(
            "SELECT assertion_id, role FROM fact_assertion_link WHERE fact_id = %s", (row[0],)
        ).fetchall()
        supporting = [a for a, role in links if role == FactAssertionRole.SUPPORTS.value]
        dissenting = [a for a, role in links if role == FactAssertionRole.DISSENTS.value]
        facts.append(
            WorkingFact(
                fact_id=row[0],
                session_id=row[1],
                concept=ConceptReference.model_validate(row[2]),
                value=row[3],
                verification_state=row[4],
                freshness=row[5],
                version=row[6],
                supporting_assertion_ids=supporting,
                dissenting_assertion_ids=dissenting,
            )
        )
    return facts


def list_conflicts(conn: psycopg.Connection, session_id: uuid.UUID) -> list[Conflict]:
    rows = conn.execute(
        """
        SELECT conflict_id, session_id, type, materiality, status, resolution_json
        FROM conflict WHERE session_id = %s
        """,
        (session_id,),
    ).fetchall()
    conflicts = []
    for row in rows:
        assertion_ids = [
            r[0]
            for r in conn.execute(
                "SELECT assertion_id FROM conflict_assertion_link WHERE conflict_id = %s",
                (row[0],),
            ).fetchall()
        ]
        conflicts.append(
            Conflict(
                conflict_id=row[0],
                session_id=row[1],
                assertion_ids=assertion_ids,
                type=row[2],
                materiality=row[3],
                status=row[4],
                resolution=row[5],
            )
        )
    return conflicts


# --------------------------------------------- requirement states + gaps

def replace_requirement_states_and_gaps(
    conn: psycopg.Connection,
    session_id: uuid.UUID,
    states: list[RequirementState],
    gaps_by_requirement_state_id: dict[uuid.UUID, list[InformationGap]],
) -> None:
    conn.execute(
        "DELETE FROM information_gap WHERE requirement_state_id IN "
        "(SELECT requirement_state_id FROM requirement_state WHERE session_id = %s)",
        (session_id,),
    )
    conn.execute("DELETE FROM requirement_state WHERE session_id = %s", (session_id,))

    for state in states:
        conn.execute(
            """
            INSERT INTO requirement_state
                (requirement_state_id, session_id, requirement_id, information_state,
                 evidence_refs_json, evaluated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                state.requirement_state_id,
                state.session_id,
                state.requirement_id,
                state.information_state.value,
                Jsonb([str(x) for x in state.evidence_refs]),
                state.evaluated_at,
            ),
        )
        for gap in gaps_by_requirement_state_id.get(state.requirement_state_id, []):
            conn.execute(
                """
                INSERT INTO information_gap
                    (gap_id, requirement_state_id, gap_type, priority_score, status,
                     resolution_options_json)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    gap.gap_id,
                    gap.requirement_state_id,
                    gap.gap_type.value,
                    gap.priority_score,
                    gap.status.value,
                    Jsonb([o.value for o in gap.resolution_options]),
                ),
            )


def list_requirement_states(
    conn: psycopg.Connection, session_id: uuid.UUID
) -> list[RequirementState]:
    rows = conn.execute(
        """
        SELECT requirement_state_id, session_id, requirement_id, information_state,
               evidence_refs_json, evaluated_at
        FROM requirement_state WHERE session_id = %s
        """,
        (session_id,),
    ).fetchall()
    return [
        RequirementState(
            requirement_state_id=r[0],
            session_id=r[1],
            requirement_id=r[2],
            information_state=r[3],
            evidence_refs=r[4] or [],
            evaluated_at=r[5],
        )
        for r in rows
    ]


def list_gaps_for_session(conn: psycopg.Connection, session_id: uuid.UUID) -> list[InformationGap]:
    rows = conn.execute(
        """
        SELECT g.gap_id, g.requirement_state_id, g.gap_type, g.priority_score,
               g.status, g.resolution_options_json
        FROM information_gap g
        JOIN requirement_state rs ON rs.requirement_state_id = g.requirement_state_id
        WHERE rs.session_id = %s
        ORDER BY g.priority_score DESC
        """,
        (session_id,),
    ).fetchall()
    return [
        InformationGap(
            gap_id=r[0],
            requirement_state_id=r[1],
            gap_type=r[2],
            priority_score=float(r[3]),
            status=r[4],
            resolution_options=r[5] or [],
        )
        for r in rows
    ]


# ----------------------------------------------------------------- tasks

def insert_task(conn: psycopg.Connection, task: OpenTask) -> None:
    conn.execute(
        """
        INSERT INTO task (task_id, session_id, type, owner_ref, priority, status, reason_json)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            task.task_id,
            task.session_id,
            task.type.value,
            task.owner_ref,
            task.priority.value,
            task.status.value,
            Jsonb(task.reason),
        ),
    )


def list_tasks(conn: psycopg.Connection, session_id: uuid.UUID) -> list[OpenTask]:
    rows = conn.execute(
        """
        SELECT task_id, session_id, type, owner_ref, priority, status, reason_json
        FROM task WHERE session_id = %s
        """,
        (session_id,),
    ).fetchall()
    return [
        OpenTask(
            task_id=r[0],
            session_id=r[1],
            type=r[2],
            owner_ref=r[3],
            priority=r[4],
            status=r[5],
            reason=r[6],
        )
        for r in rows
    ]


# --------------------------------------------------------- agenda items

def insert_agenda_item(conn: psycopg.Connection, item: PatientAgendaItem) -> None:
    conn.execute(
        """
        INSERT INTO patient_agenda_item
            (agenda_item_id, session_id, text, priority, status, source_turn_id)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            item.agenda_item_id,
            item.session_id,
            item.text,
            item.priority.value,
            item.status.value,
            item.source_turn_id,
        ),
    )


def list_agenda_items(conn: psycopg.Connection, session_id: uuid.UUID) -> list[PatientAgendaItem]:
    rows = conn.execute(
        """
        SELECT agenda_item_id, session_id, text, priority, status, source_turn_id
        FROM patient_agenda_item WHERE session_id = %s
        """,
        (session_id,),
    ).fetchall()
    return [
        PatientAgendaItem(
            agenda_item_id=r[0],
            session_id=r[1],
            text=r[2],
            priority=r[3],
            status=r[4],
            source_turn_id=r[5],
        )
        for r in rows
    ]


# ------------------------------------------- interview actions and turns

def insert_interview_action(conn: psycopg.Connection, action: InterviewAction) -> None:
    contract = action.model_dump(
        mode="json", exclude={"action_id", "session_id", "action_type", "status"}
    )
    conn.execute(
        """
        INSERT INTO interview_action (action_id, session_id, action_type, contract_json, status)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (action.action_id, action.session_id, action.action_type.value, Jsonb(contract),
         action.status.value),
    )


def get_interview_action(conn: psycopg.Connection, action_id: uuid.UUID) -> InterviewAction:
    row = conn.execute(
        """
        SELECT action_id, session_id, action_type, contract_json, status
        FROM interview_action WHERE action_id = %s
        """,
        (action_id,),
    ).fetchone()
    if row is None:
        raise KeyError(f"InterviewAction {action_id} not found")
    return InterviewAction(action_id=row[0], session_id=row[1], action_type=row[2], status=row[4], **row[3])


def set_interview_action_status(
    conn: psycopg.Connection, action_id: uuid.UUID, status: InterviewActionStatus
) -> None:
    conn.execute(
        "UPDATE interview_action SET status = %s WHERE action_id = %s", (status.value, action_id)
    )


def asked_targets(conn: psycopg.Connection, session_id: uuid.UUID) -> set[str]:
    """Every requirement_id an InterviewAction has already targeted in
    this session -- so an answered-but-still-open gap (e.g. patient-only,
    unverified) is never asked twice."""
    rows = conn.execute(
        """
        SELECT DISTINCT jsonb_array_elements_text(contract_json -> 'targets')
        FROM interview_action WHERE session_id = %s
        """,
        (session_id,),
    ).fetchall()
    return {r[0] for r in rows}


def insert_turn(conn: psycopg.Connection, turn: Turn) -> None:
    conn.execute(
        """
        INSERT INTO turn (turn_id, session_id, action_id, speaker, modality, content, confidence, occurred_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (turn.turn_id, turn.session_id, turn.action_id, turn.speaker.value, turn.modality.value,
         turn.content, turn.confidence, turn.occurred_at),
    )


def list_turns(
    conn: psycopg.Connection, session_id: uuid.UUID, action_id: uuid.UUID | None = None
) -> list[Turn]:
    query = """
        SELECT turn_id, session_id, action_id, speaker, modality, content, confidence, occurred_at
        FROM turn WHERE session_id = %s
    """
    params: tuple[Any, ...] = (session_id,)
    if action_id is not None:
        query += " AND action_id = %s"
        params = (session_id, action_id)
    rows = conn.execute(query + " ORDER BY occurred_at, turn_id", params).fetchall()
    return [
        Turn(turn_id=r[0], session_id=r[1], action_id=r[2], speaker=r[3], modality=r[4],
             content=r[5], confidence=float(r[6]) if r[6] is not None else None, occurred_at=r[7])
        for r in rows
    ]
