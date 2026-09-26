from __future__ import annotations

import os
from collections.abc import Iterator

import psycopg

from periop_core.db import get_release_manifest, insert_release_manifest
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


# The demo runs a single fixed ReleaseManifest (INV-012: pinned per
# session, immutable except via governed migration -- there is no
# migration workflow in this demo, so one manifest serves every session).
_DEMO_MANIFEST_ID: str | None = None


def get_demo_manifest(conn: psycopg.Connection) -> ReleaseManifest:
    global _DEMO_MANIFEST_ID
    if _DEMO_MANIFEST_ID is not None:
        return get_release_manifest(conn, _DEMO_MANIFEST_ID)

    row = conn.execute(
        "SELECT manifest_id FROM release_manifest ORDER BY created_at LIMIT 1"
    ).fetchone()
    if row is not None:
        _DEMO_MANIFEST_ID = row[0]
        return get_release_manifest(conn, row[0])

    manifest = ReleaseManifest(
        clinical_dataset_version="1.0.1",
        rules_version="0.1.0-demo",
        terminology_version="unpinned",
        prompt_version="0.1.0-demo",
        extractor_model_id="none (demo: assertions entered directly)",
        language_model_id="none (demo: no LLM in the loop)",
        validator_version="0.1.0-demo",
        fhir_mapping_version="0.1.0-demo",
        site_configuration_version="demo",
    )
    insert_release_manifest(conn, manifest)
    _DEMO_MANIFEST_ID = manifest.manifest_id
    return manifest
