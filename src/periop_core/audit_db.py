"""Persistence for SVC-014 (Audit & Provenance Service), against
db/migrations/0003_audit_trail.sql. Follows the same patterns as
periop_core.db (kept as a separate module purely to keep file size
manageable -- see that module's docstring).

Only two operations, matching the spec table's own naming: `append_event`
and `get_lineage`. There is deliberately no update/delete function --
db/migrations/0003_audit_trail.sql's triggers reject those at the DB
layer, so this module doesn't even try to offer them.

"Clinical mutation fails if provenance unavailable" (SVC-014's acceptance
test) isn't special-cased here: callers (periop_api) run `append_event`
in the same transaction as the mutation it records, using the existing
per-request connection (see periop_api.deps.get_conn) -- so if the audit
insert fails, the whole request rolls back along with it, for free.
"""
from __future__ import annotations

import uuid

import psycopg
from psycopg.types.json import Jsonb

from periop_core.models import AuditEvent


def append_event(conn: psycopg.Connection, event: AuditEvent) -> None:
    conn.execute(
        """
        INSERT INTO audit_event
            (event_id, session_id, event_type, entity_type, entity_id,
             payload_json, occurred_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            event.event_id,
            event.session_id,
            event.event_type.value,
            event.entity_type,
            event.entity_id,
            Jsonb(event.payload),
            event.occurred_at,
        ),
    )


def get_lineage(conn: psycopg.Connection, session_id: uuid.UUID) -> list[AuditEvent]:
    """All of a session's audit events, oldest first -- the order a
    reconstruction/replay would need."""
    rows = conn.execute(
        """
        SELECT event_id, session_id, event_type, entity_type, entity_id,
               payload_json, occurred_at
        FROM audit_event WHERE session_id = %s ORDER BY occurred_at
        """,
        (session_id,),
    ).fetchall()
    return [
        AuditEvent(
            event_id=r[0],
            session_id=r[1],
            event_type=r[2],
            entity_type=r[3],
            entity_id=r[4],
            payload=r[5],
            occurred_at=r[6],
        )
        for r in rows
    ]
