"""Service layer: the only code path permitted to create/mutate canonical
objects (INV-013 — raw model/candidate output cannot directly mutate
clinical truth).

Only `session_service` has a real implementation so far. The rest of the
service catalogue (Table 13: Orchestrator, Clinical State, Requirement &
Gap, Safety, LLM Extraction/Language, Response Validator, Terminology,
FHIR Adapter, Retrieval, Workflow Task, Audit & Provenance, Configuration
Registry) is Phase 2+ (conversational shell, integration) and Phase 3+
(FHIR) per Table 24, and is intentionally not scaffolded here yet rather
than stubbed with misleading empty classes.
"""
