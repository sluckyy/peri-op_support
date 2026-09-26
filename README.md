# peri-op_support

Perioperative Conversational AI — governed specification and the
beginnings of its deterministic clinical core.

This is early-stage: a specification repository that is just starting to
grow real code. Read this file before assuming anything here is
production-ready — several sections below say plainly what's real and
what's still a placeholder.

## Repository layout

```
docs/
  source/     Authoritative specification artefacts (docx/xlsx), as
              produced by the scoping-review/design process. Treat these
              as the source of truth; everything else derives from them.
  exports/    Generated, diffable CSV/Markdown views of the workbook
              sheets and narrative documents, for review in pull requests
              without opening Excel/Word. Regenerate with
              `python3 scripts/export_dataset.py`. Never hand-edit.
  addenda/    Working addenda to the source specification that haven't
              yet been folded back into a new source-document revision.
              Currently: v1.1-gap-remediation.md.

src/periop_core/   The deterministic clinical core (Python). See "What's
                    implemented" below for exactly how much of Phase 1
                    (Full Spec Table 24) this currently covers.

db/migrations/      PostgreSQL DDL for the canonical schema (Full Spec
                    Table 28), validated against a real Postgres 16
                    instance, not just hand-written.

tests/              pytest suite for everything in src/periop_core.

scripts/            Utility scripts (currently just the docs exporter).
```

## Specification documents

The governing specification is
`docs/source/Perioperative_Conversational_AI_Full_Project_and_Technical_Specification_v1.0.docx`
(readable copy: `docs/exports/full_project_specification_v1.0.md`), which
consolidates the earlier scoping review, clinical dataset, provenance/
reconciliation model and interoperability design into one document. Six
gaps identified in review of v1.0 — and the product/governance decisions
made to resolve them — are recorded in
`docs/addenda/v1.1-gap-remediation.md`. Read that addendum alongside v1.0;
it is not yet folded into a new docx revision.

**One item in the addendum is an unresolved, blocking prerequisite, not a
decision:** real-time clinical handoff staffing during pilot hours. The
system's safety design (fail-closed to human handoff) depends on it. See
addendum item 3.

## What's implemented (honest accounting against Full Spec Table 24, Phase 1)

Phase 1 ("Deterministic core... all existing deterministic regression
cases pass without LLM") asks for: Session, assertion graph, requirements/
gaps, reconciliation, safety gates, task ownership, audit.

| Component | Status |
|---|---|
| Canonical object models (Session, Assertion, WorkingFact, Conflict, RequirementState, InformationGap, InterviewAction, Turn, OpenTask/Task, Cue, PatientAgendaItem, ReleaseManifest) | **Implemented**, with the model-level invariants from Table 20 that can be checked on a single object (INV-001, INV-003, and a self-supersession check) enforced as pydantic validators. |
| PostgreSQL schema | **Implemented** (`db/migrations/0001_init.sql`) and validated by actually running it against Postgres 16, including exercising the `assertion_provenance_not_empty` CHECK constraint. Cross-object invariants (e.g. INV-003 properly) are *not* enforced at the DB layer — see the comment in the migration file — only in the Python model layer, which is the intended access path (INV-013). |
| Clinical Dataset loader | **Implemented** (`periop_core.dataset`) — loads all 343 concepts from the CSV export with their `Requirement_class`. |
| Source Authority Matrix loader | **Implemented** (`periop_core.source_authority`) — loads the matrix; exposes a conservative auto-resolution flag. Not yet wired into reconciliation's tie-breaking (see below). |
| Reconciliation engine | **Partially implemented** (`periop_core.reconciliation`). Groups assertions by concept, builds a WorkingFact when they agree, and raises a classified Conflict (never dropping an assertion) when they disagree. **Not implemented**: freshness assessment (step 3), fitness-based tie-breaking using the Source Authority Matrix (step 4 proper — the matrix loads but isn't used to auto-resolve yet), conversational clarification / collateral retrieval / human verification (steps 8-10), and FHIR projection (step 12). `reconciliation.py`'s docstring states this scope directly. |
| Gap engine | **Partially implemented** (`periop_core.gap_engine`). Computes RequirementState from WorkingFacts and produces prioritised InformationGaps, respecting INV-005 (12-state taxonomy, no collapsing) and INV-006 (no gap from a NOT_APPLICABLE requirement). **Not implemented**: parsing the dataset's free-text `Trigger` column into actual conditional-activation logic — every non-M0 requirement is currently treated as always-active, which is a documented simplification, not a hidden shortcut. |
| Safety / closure gate | **Partially implemented** (`periop_core.safety`). Implements the closure-gate decision (COMPLETE / COMPLETE_WITH_OPEN_ACTIONS / BLOCKED) per INV-010/014. **Not implemented**: red-flag rule *evaluation* (the dataset's `Red_flag_rule` column is prose, not yet a structured predicate), the escalation classes (ESC-001..012), and the safety-interrupt policy hierarchy (§7.1) — these need the conversation orchestrator, which is Phase 2. |
| Eligibility check | **Implemented** (`periop_core.eligibility`) — new in the v1.1 addendum, not in the original v1.0 spec. Age/obstetric/emergency-listing checks, hard-fails closed on unknown data. |
| Session service | **Minimal implementation** (`periop_core.services.session_service`) — session creation gated on eligibility, activation gated on the addendum's INV-017 (AI-role notice acknowledgement). |
| Audit/provenance trail | **Not implemented.** `provenance_json`/`Provenance` fields exist in the schema and models, but there's no append-only audit event log or replay capability yet (SVC-014, INV-008). |
| LLM extraction/language, conversation orchestrator, InterviewAction selection, validator stack, FHIR adapter, API/event layer | **Not implemented** — these are Phase 2/3 per Table 24 and were deliberately left out of this pass rather than stubbed with empty classes that would misrepresent progress. |

## Running the tests

```
pip install -e .
python3 -m pytest -q
```

29 tests currently pass, covering the invariants above and the
reconciliation/gap-engine/closure/eligibility scenarios modelled on
`docs/exports/reconciliation_test_cases.csv`. Where a test pins down a
*documented current limitation* (e.g. the engine not yet resolving a
stale-vs-current conflict via freshness), its docstring says so — it is
not asserting that behaviour is correct, only that it's what the code
does right now.

## Regenerating the doc exports

```
python3 scripts/export_dataset.py
```

## License / status

Working specification and prototype code — not a clinical guideline, not
validated, not approved for any patient-facing use. See
`docs/source/...Full_Project_and_Technical_Specification_v1.0.docx`
§"Document status".
