"""Demo API for periop_core (Phase 1 deterministic core), built against a
useful subset of the Full Spec's Table 17 endpoints.

Scope honestly stated: this is a DEMO harness, not the production API.
Assertions reach the store two ways:

- `POST /sessions/{id}/interview/next` + `.../interview/answer` -- the
  conversational interviewer. Each question is a persisted InterviewAction
  (INV-007); the patient's reply is a Turn; Claude (LLM-001) proposes a
  *candidate* answer for the one concept asked, and only what passes the
  deterministic validator in periop_core.interview_llm is recorded, with
  the patient's own words kept verbatim. This is the real ingestion shape,
  minus the full orchestrator (no cue tracking, agenda, or safety
  interrupts yet).
- `POST /sessions/{id}/assertions` -- the original demo shortcut, which
  lets a caller add an Assertion directly. Kept as the manual fallback
  form (and the interviewer's fail-closed path when no LLM is available);
  clearly named and documented as a shortcut, not disguised as a real
  ingestion path.
"""
