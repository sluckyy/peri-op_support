"""DB-backed tests need a real Postgres instance. They're skipped
automatically if one isn't reachable (e.g. in a CI runner without
Postgres) rather than failing the whole suite.

Local dev: `service postgresql start` then run pytest as normal --
`db_conn` creates/migrates/drops a scratch database per test session.
"""
from __future__ import annotations

import os
import pathlib

import psycopg
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
MIGRATION_SQL = REPO_ROOT / "db" / "migrations" / "0001_init.sql"

ADMIN_CONNINFO = os.environ.get("PERIOP_TEST_ADMIN_CONNINFO", "dbname=postgres")
TEST_DB_NAME = "periop_pytest"


def _postgres_reachable() -> bool:
    try:
        with psycopg.connect(ADMIN_CONNINFO, connect_timeout=2):
            return True
    except psycopg.OperationalError:
        return False


@pytest.fixture(scope="session")
def db_conninfo():
    if not _postgres_reachable():
        pytest.skip("No local Postgres reachable for DB-backed tests")

    with psycopg.connect(ADMIN_CONNINFO, autocommit=True) as admin_conn:
        admin_conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}")
        admin_conn.execute(f"CREATE DATABASE {TEST_DB_NAME}")

    test_conninfo = ADMIN_CONNINFO.replace("dbname=postgres", f"dbname={TEST_DB_NAME}")
    if "dbname=" not in test_conninfo:
        test_conninfo = f"{test_conninfo} dbname={TEST_DB_NAME}"

    with psycopg.connect(test_conninfo, autocommit=True) as conn:
        conn.execute(MIGRATION_SQL.read_text())

    yield test_conninfo

    with psycopg.connect(ADMIN_CONNINFO, autocommit=True) as admin_conn:
        admin_conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}")


@pytest.fixture()
def db_conn(db_conninfo):
    with psycopg.connect(db_conninfo) as conn:
        yield conn
        conn.rollback()
