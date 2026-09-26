"""Demo API for periop_core (Phase 1 deterministic core), built against a
useful subset of the Full Spec's Table 17 endpoints.

Scope honestly stated: this is a DEMO harness, not the production API.
The most important shortcut it takes is `POST /sessions/{id}/assertions`,
which lets a caller add an Assertion directly. The real system never does
this -- Assertions are only ever produced by the (unbuilt) LLM extraction
service from a patient Turn, validated, and passed through the
orchestrator (INV-013, INV-007). This endpoint exists so the deterministic
core can be exercised and demoed before that pipeline is built. It is
clearly named and documented as a demo shortcut in the OpenAPI docs
(see app.py), not disguised as a real ingestion path.
"""
