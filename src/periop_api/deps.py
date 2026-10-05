from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import anthropic
import psycopg

from periop_core.db import get_release_manifest, insert_release_manifest
from periop_core.interview_llm import PROMPT_VERSION, llm_model
from periop_core.models import ReleaseManifest

DEFAULT_DEV_CONNINFO = "dbname=periop_core"


def database_url() -> str:
    return os.environ.get("PERIOP_DATABASE_URL", DEFAULT_DEV_CONNINFO)


def get_conn() -> Iterator[psycopg.Connection]:
    with psycopg.connect(database_url()) as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def get_llm_client() -> anthropic.Anthropic | None:
    """None when no key is configured -- the interviewer then fails closed
    (503) and the UI falls back to the manual form. Short timeout: a
    patient is waiting on the other end of a voice turn."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    return anthropic.Anthropic(timeout=30.0, max_retries=1)


# INV-012: a session is pinned to the manifest current when it was
# created. The manifest records which models/prompts are in the loop, so
# when that configuration changes a new manifest is created for new
# sessions while existing sessions keep theirs. No governed migration
# workflow in this demo -- matching is by content.
_DEMO_MANIFEST_ID: uuid.UUID | None = None
_DEMO_MANIFEST_KEY: dict | None = None
_IDENTITY_FIELDS = {"manifest_id", "created_at"}


def _current_manifest() -> ReleaseManifest:
    model = llm_model()
    return ReleaseManifest(
        clinical_dataset_version="1.0.1",
        rules_version="0.1.0-demo",
        terminology_version="unpinned",
        prompt_version=PROMPT_VERSION,
        extractor_model_id=f"{model} (LLM-001 turn extraction)",
        language_model_id=f"{model} (LLM-003 question realisation)",
        validator_version="0.2.0-demo",
        fhir_mapping_version="0.1.0-demo",
        site_configuration_version="demo",
    )


def get_demo_manifest(conn: psycopg.Connection) -> ReleaseManifest:
    global _DEMO_MANIFEST_ID, _DEMO_MANIFEST_KEY
    wanted = _current_manifest()
    key = wanted.model_dump(mode="json", exclude=_IDENTITY_FIELDS)
    if _DEMO_MANIFEST_ID is not None and _DEMO_MANIFEST_KEY == key:
        return get_release_manifest(conn, _DEMO_MANIFEST_ID)

    for (manifest_id,) in conn.execute(
        "SELECT manifest_id FROM release_manifest ORDER BY created_at"
    ).fetchall():
        existing = get_release_manifest(conn, manifest_id)
        if existing.model_dump(mode="json", exclude=_IDENTITY_FIELDS) == key:
            _DEMO_MANIFEST_ID, _DEMO_MANIFEST_KEY = existing.manifest_id, key
            return existing

    insert_release_manifest(conn, wanted)
    _DEMO_MANIFEST_ID, _DEMO_MANIFEST_KEY = wanted.manifest_id, key
    return wanted
