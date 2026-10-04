"""Round-trip and immutability tests for periop_core.audit_db (SVC-014)
against a real Postgres instance -- see conftest.py, skipped if none is
reachable."""
import psycopg
import pytest

from periop_core.audit_db import append_event, get_lineage
from periop_core.enums import AuditEventType, EligibilityResult
from periop_core.models import AuditEvent, ReleaseManifest, Session


def _manifest():
    return ReleaseManifest(
        clinical_dataset_version="1.0.1",
        rules_version="0.1.0",
        terminology_version="unpinned",
        prompt_version="0.1.0",
        extractor_model_id="none",
        language_model_id="none",
        validator_version="0.1.0",
        fhir_mapping_version="0.1.0",
        site_configuration_version="demo",
    )


def _session(manifest_id):
    return Session(
        subject_ref="pt-audit",
        manifest_id=manifest_id,
        eligibility_result=EligibilityResult.ELIGIBLE,
    )


def test_get_lineage_returns_events_oldest_first(db_conn):
    from periop_core.db import insert_release_manifest, insert_session

    manifest = _manifest()
    insert_release_manifest(db_conn, manifest)
    session = _session(manifest.manifest_id)
    insert_session(db_conn, session)

    append_event(
        db_conn,
        AuditEvent(
            session_id=session.session_id,
            event_type=AuditEventType.SESSION_CREATED,
            entity_type="session",
            entity_id=session.session_id,
            payload={"subject_ref": "pt-audit"},
        ),
    )
    append_event(
        db_conn,
        AuditEvent(
            session_id=session.session_id,
            event_type=AuditEventType.NOTICE_ACKNOWLEDGED,
            entity_type="session",
            entity_id=session.session_id,
        ),
    )

    lineage = get_lineage(db_conn, session.session_id)
    assert [e.event_type for e in lineage] == [
        AuditEventType.SESSION_CREATED,
        AuditEventType.NOTICE_ACKNOWLEDGED,
    ]
    assert lineage[0].occurred_at <= lineage[1].occurred_at
    assert lineage[0].payload == {"subject_ref": "pt-audit"}


def test_lineage_is_empty_for_a_session_with_no_events(db_conn):
    from periop_core.db import insert_release_manifest, insert_session

    manifest = _manifest()
    insert_release_manifest(db_conn, manifest)
    session = _session(manifest.manifest_id)
    insert_session(db_conn, session)

    assert get_lineage(db_conn, session.session_id) == []


def test_audit_event_rejects_update_and_delete(db_conn):
    """SVC-014: 'Immutable lineage', enforced by the DB triggers in
    0003_audit_trail.sql, not just application convention."""
    from periop_core.db import insert_release_manifest, insert_session

    manifest = _manifest()
    insert_release_manifest(db_conn, manifest)
    session = _session(manifest.manifest_id)
    insert_session(db_conn, session)

    event = AuditEvent(
        session_id=session.session_id,
        event_type=AuditEventType.SESSION_CREATED,
        entity_type="session",
        entity_id=session.session_id,
    )
    append_event(db_conn, event)

    # Each attempt runs in its own savepoint (psycopg's nested
    # conn.transaction()) so the trigger's raised exception only unwinds
    # that attempt, not the session/event rows inserted above.
    with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
        with db_conn.transaction():
            db_conn.execute(
                "UPDATE audit_event SET entity_type = 'tampered' WHERE event_id = %s",
                (event.event_id,),
            )

    with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
        with db_conn.transaction():
            db_conn.execute("DELETE FROM audit_event WHERE event_id = %s", (event.event_id,))

    # The row survived both attempts, untouched.
    assert get_lineage(db_conn, session.session_id)[0].entity_type == "session"
