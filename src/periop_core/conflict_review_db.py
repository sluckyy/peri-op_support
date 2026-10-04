"""Persistence for ConflictReview (periop_core.models), against
db/migrations/0006_conflict_review.sql. Deliberately NOT part of
periop_core.db: that module's WorkingFact/Conflict rows are recomputed
wholesale on every reconciliation pass, and a ConflictReview must
survive that -- see ConflictReview's own docstring. Append-once /
targeted-update-only, the same shape as periop_core.model_layer_db's
functions, kept in its own module purely to keep file size manageable.
"""
from __future__ import annotations

import uuid

import psycopg
from psycopg.types.json import Jsonb

from periop_core.models import (
    ConceptReference,
    ConflictResolution,
    ConflictReview,
    ConflictReviewSide,
)


def insert_conflict_review(conn: psycopg.Connection, review: ConflictReview) -> None:
    conn.execute(
        """
        INSERT INTO conflict_review
            (review_id, session_id, conflict_id, concept_json, sides_json,
             status, resolution_json, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            review.review_id,
            review.session_id,
            review.conflict_id,
            Jsonb(review.concept.model_dump(mode="json")),
            Jsonb([s.model_dump(mode="json") for s in review.sides]),
            review.status.value,
            Jsonb(review.resolution.model_dump(mode="json")) if review.resolution else None,
            review.created_at,
        ),
    )


def get_conflict_review(conn: psycopg.Connection, review_id: uuid.UUID) -> ConflictReview:
    row = conn.execute(
        """
        SELECT review_id, session_id, conflict_id, concept_json, sides_json,
               status, resolution_json, created_at
        FROM conflict_review WHERE review_id = %s
        """,
        (review_id,),
    ).fetchone()
    if row is None:
        raise KeyError(f"ConflictReview {review_id} not found")
    return _row_to_review(row)


def list_conflict_reviews(conn: psycopg.Connection, session_id: uuid.UUID) -> list[ConflictReview]:
    rows = conn.execute(
        """
        SELECT review_id, session_id, conflict_id, concept_json, sides_json,
               status, resolution_json, created_at
        FROM conflict_review WHERE session_id = %s ORDER BY created_at
        """,
        (session_id,),
    ).fetchall()
    return [_row_to_review(r) for r in rows]


def update_conflict_review_resolution(conn: psycopg.Connection, review: ConflictReview) -> None:
    conn.execute(
        """
        UPDATE conflict_review SET status = %s, resolution_json = %s WHERE review_id = %s
        """,
        (
            review.status.value,
            Jsonb(review.resolution.model_dump(mode="json")) if review.resolution else None,
            review.review_id,
        ),
    )


def _row_to_review(row) -> ConflictReview:
    return ConflictReview(
        review_id=row[0],
        session_id=row[1],
        conflict_id=row[2],
        concept=ConceptReference(**row[3]),
        sides=[ConflictReviewSide(**s) for s in row[4]],
        status=row[5],
        resolution=ConflictResolution(**row[6]) if row[6] else None,
        created_at=row[7],
    )
