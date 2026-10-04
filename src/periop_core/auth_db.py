"""Persistence for periop_core.auth's User/AuthSession, against
db/migrations/0008_auth.sql. Kept separate from periop_core.db purely
to keep file size manageable, same rationale as audit_db.py and
model_layer_db.py.
"""
from __future__ import annotations

import uuid

import psycopg

from periop_core.auth import AuthSession, User


def insert_user(conn: psycopg.Connection, user: User) -> None:
    conn.execute(
        """
        INSERT INTO app_user (user_id, username, password_hash, created_at)
        VALUES (%s, %s, %s, %s)
        """,
        (user.user_id, user.username, user.password_hash, user.created_at),
    )


def get_user_by_username(conn: psycopg.Connection, username: str) -> User | None:
    row = conn.execute(
        "SELECT user_id, username, password_hash, created_at FROM app_user WHERE username = %s",
        (username,),
    ).fetchone()
    if row is None:
        return None
    return User(user_id=row[0], username=row[1], password_hash=row[2], created_at=row[3])


def get_user_by_id(conn: psycopg.Connection, user_id: uuid.UUID) -> User | None:
    row = conn.execute(
        "SELECT user_id, username, password_hash, created_at FROM app_user WHERE user_id = %s",
        (user_id,),
    ).fetchone()
    if row is None:
        return None
    return User(user_id=row[0], username=row[1], password_hash=row[2], created_at=row[3])


def insert_session(conn: psycopg.Connection, session: AuthSession) -> None:
    conn.execute(
        """
        INSERT INTO auth_session (token, user_id, created_at, expires_at)
        VALUES (%s, %s, %s, %s)
        """,
        (session.token, session.user_id, session.created_at, session.expires_at),
    )


def get_session(conn: psycopg.Connection, token: str) -> AuthSession | None:
    row = conn.execute(
        "SELECT token, user_id, created_at, expires_at FROM auth_session WHERE token = %s",
        (token,),
    ).fetchone()
    if row is None:
        return None
    return AuthSession(token=row[0], user_id=row[1], created_at=row[2], expires_at=row[3])


def delete_session(conn: psycopg.Connection, token: str) -> None:
    conn.execute("DELETE FROM auth_session WHERE token = %s", (token,))
