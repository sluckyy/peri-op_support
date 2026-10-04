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

src/periop_api/     A demo REST API (FastAPI) over periop_core, so the
                    core can actually be exercised over HTTP instead of
                    only in unit tests. See its own "Scope honestly
                    stated" docstring in __init__.py -- most importantly,
                    it has one deliberate demo shortcut (a direct
                    "add assertion" endpoint) that does not exist in the
                    real system's design.

frontend/           A small Vue 3 + Vite single-page demo UI over
                    periop_api: start a session, add assertions, watch
                    working facts / conflicts / gaps / closure update
                    live. Built and exercised in a real browser
                    (Playwright), not just built successfully.

db/migrations/      PostgreSQL DDL for the canonical schema (Full Spec
                    Table 28), validated against a real Postgres 16
                    instance, not just hand-written.

Dockerfile           Multi-stage build: compiles the Vue frontend, then
                    packages it with periop_api into one Python runtime
                    image (one container instead of a separate static
                    site + API, to minimise Azure resources for the
                    demo). NOTE: this sandbox has no Docker daemon, so
                    `docker build` itself has not been run against this
                    file. Its runtime logic (editable install + static
                    file serving from a separate directory) *was*
                    validated, by manually replicating the image's file
                    layout in a plain venv and confirming both the API
                    and the built frontend serve correctly from it --
                    see the git history for that check. Run an actual
                    `docker build .` (or `az acr build`, see below)
                    before trusting the Dockerfile syntax itself.

tests/              pytest suite for everything in src/periop_core and
                    src/periop_api (including HTTP-level tests via
                    FastAPI's TestClient against a real Postgres
                    instance, not mocks).

scripts/            Utility scripts (currently just the docs exporter).
```

## Specification documents

The base specification is
`docs/source/Perioperative_Conversational_AI_Full_Project_and_Technical_Specification_v1.0.docx`
(readable copy: `docs/exports/full_project_specification_v1.0.md`), which
consolidates the earlier scoping review, clinical dataset, provenance/
reconciliation model and interoperability design into one document.

**Two independent, not-yet-merged v1.1 extensions sit on top of it:**
- `docs/addenda/v1.1-gap-remediation.md` — six gaps identified in review
  of v1.0 and the product/governance decisions made to resolve them
  (consent model, intake eligibility, staffing, DSAR, regulatory anchor,
  outcome-calibration deferral).
- `docs/source/..._v1.1_Model_Layer.docx` (readable copy:
  `docs/exports/full_project_specification_v1.1_model_layer.md`) — adds
  §6A, the conversational Model Layer: a formal state model, epistemic
  grounding ladder, repair/truth-maintenance, attention-bounded working
  memory, psychological safety, personal adaptation, causal-hypothesis
  reasoning and an expanded action vocabulary, sitting between raw
  conversation and the (not-yet-built) Conversation Orchestrator.

Read all three alongside each other; neither v1.1 document is aware of
the other's changes.

**One item in the gap-remediation addendum is an unresolved, blocking
prerequisite, not a decision:** real-time clinical handoff staffing
during pilot hours. The system's safety design (fail-closed to human
handoff) depends on it. See addendum item 3.

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
| Audit/provenance trail | **Partially implemented** (`periop_core.audit_db`, `db/migrations/0003_audit_trail.sql`). SVC-014's `appendEvent`/`getLineage` for the Phase 1 core session/assertion lifecycle (session created, AI-role notice acknowledged, session activated, an assertion added, session closed) — immutability enforced at the DB layer by triggers that reject `UPDATE`/`DELETE` on `audit_event`, not just application convention. Exposed as `GET /api/sessions/{id}/audit` and shown live in the demo UI. **Not implemented**: v1.1 Model Layer mutations (hypotheses, repairs, obligations, psychological-safety signals) aren't wired into the trail yet; `provenance_json`/`Provenance` fields on individual objects (a related but distinct mechanism) predate this and are unchanged. |
| Persistence (`periop_core.db`) | **Implemented** for everything above — Session, Assertion, WorkingFact/Conflict (recomputed each reconciliation pass, not versioned), RequirementState/InformationGap (same), Task, PatientAgendaItem. Round-trip tested against real Postgres. Concurrency control (NFR-003) is **not implemented** -- see the module docstring. |
| Demo API (`periop_api`) | **Implemented**: create session (with eligibility gate), acknowledge AI notice, activate, add assertion (demo shortcut), get summary, attempt closure, list concepts. HTTP-level tested (FastAPI TestClient + real Postgres), not just unit tested. **Not implemented**: the real Table 17 API surface (Turn submission through the orchestrator, FHIR projection/commit endpoints), auth, and the audit/event trail. |
| Demo frontend | **Implemented**: a single Vue page exercising the full demo flow, including the eligibility-rejection path and a live safety-critical-conflict scenario. Confirmed working in an actual headless-Chromium run, not just `npm run build` succeeding. |
| LLM extraction/language, conversation orchestrator, InterviewAction selection, validator stack, FHIR adapter, real event architecture | **Not implemented** — these are Phase 2/3 per Table 24 and were deliberately left out rather than stubbed with empty classes that would misrepresent progress. |

## v1.1 Model Layer status (against Table 13's MVP-required list)

The Model Layer (§6A) sits conceptually between raw conversation and the
Conversation Orchestrator — but the Orchestrator itself isn't built yet
(see the Phase 1 table above), so none of this is wired into a live
*conversation loop* (there's no LLM turning patient speech into these
objects automatically). What's real: the underlying data model, the
epistemic/causal/psychological-safety/humour reasoning, persistence
(`db/migrations/0002_model_layer.sql`, `periop_core.model_layer_db`),
and a full round-trip through the demo API and Vue UI — you can create a
hypothesis, attempt (and get blocked from) an ungrounded promotion, then
promote it properly with evidence; log a repair, defer it (which
requires an obligation), resolve it; watch a CRITICAL open repair block
session closure end-to-end through the UI; apply psychological-safety
signals and watch the estimate move; check the humour gate; and run the
causal-discrimination calculator — all exercised in a real headless-
browser run, not just built.

| Table 13 capability | Status |
|---|---|
| Shared Meaning Workspace (GroundedProposition, ConversationalHypothesis, Uncertainty, Contradiction) | **Implemented and in the demo** for propositions/hypotheses (create + promote via the UI). GroundedProposition is floored at L4 (patient-grounded); ConversationalHypothesis is capped below L4 — enforced as pydantic validators. Uncertainty/Contradiction have DB persistence (`periop_core.model_layer_db`) but no dedicated UI yet — read/write them directly if needed. |
| Epistemic ladder and provenance | **Implemented and in the demo**. `periop_core.epistemic.can_promote()` enforces both spec-mandated gates: L2→L4+ requires grounding evidence, →L6 requires clinician adjudication; the UI's "Promote" button surfaces a blocked attempt's exact reason (verified in a browser run, not just a test). |
| Repair queue and dependency-aware correction | **Implemented and in the demo**. Logging a DEFERRED repair without a reason *and* obligation is rejected (422); the UI creates the linked `ProspectiveObligation` inline. An OPEN CRITICAL repair blocks session closure through the full stack (core → API → UI), confirmed visually. `periop_core.model_layer_gate.find_dependents` (correction-propagation) is implemented and unit-tested but not yet exposed in the demo UI. |
| Patient agenda and prospective obligations | **Implemented** — PatientAgendaItem already existed (Phase 1); `ProspectiveObligation` is new, has no silent-expiry status, and is created/displayed via the repair-deferral flow in the demo. |
| Working-memory/attention selection | **Implemented, not in the demo**. A real, tested weighted-sum implementation of Attention_i(t) in `periop_core.attention`, including forced inclusion of high-risk items beyond the working-set size cap. Not surfaced in the UI — there's no live conversation feed of candidate items to rank yet. **Documented limitation**: the weights are a reasonable starting point, not a calibrated set. |
| Psychological-safety actions: humility, normalisation, invite correction | **Partially implemented and in the demo** for the PSt estimate itself: `periop_core.psychological_safety`'s bounded, named-signal heuristic is applied and persisted per-session, with signal buttons in the UI. Explicitly *not* a validated psychological measure (see its docstring). The action classes (INVITE_CORRECTION, ACKNOWLEDGE_LIMITATION, NORMALISE, etc.) exist in `ActionType` but nothing selects them in a live conversation — that's Orchestrator work. |
| Interaction adaptation within approved bounds | **Data model only**, not in the demo. `PersonalAdaptationState` exists with bounded fields; there is no update logic yet (would need real interaction data to adapt from, which requires the conversational shell). |
| Causal hypothesis representation | **Implemented and in the demo** as a standalone calculator (not tied to stored `CausalHypothesis` rows yet). Real Shannon-entropy-based `expected_clinical_discrimination` (ECD) in `periop_core.causal_reasoning` — verified against hand-computed values for a perfectly discriminating question (ECD = full prior entropy) and an uninformative one (ECD = 0), and exercised live via `POST /api/tools/causal-ecd`. `CausalHypothesis.status` cannot reach ADJUDICATED without an explicit clinician marker; the object has DB persistence but no dedicated create/list UI yet. |
| Affiliative humour | **Implemented and in the demo, off by default** (`periop_core.humour_policy`). `is_humour_permitted` gates on the feature flag first — every other suppression condition (distress, safety disclosure, conflict, bereavement, uncertain receptivity, patient-directed target, implied incompetence) is enforced, tested, and checkable live via the UI's humour-check form. |
| Continuous-time silence/turn model (6A.6) | **Not implemented** — correctly deferred per Table 13 ("deferred to voice implementation"); this is a text-first MVP. |
| Population policy learning (6A.14) | **Not implemented** — correctly out of scope per Table 13 ("offline research/governance capability, not autonomous MVP runtime"). |
| `ConversationStateEnvelope` (Table 11, the Model Layer → Orchestrator contract) | **Data model only**. The object exists and validates its own internal consistency (e.g. an action class can't be both recommended and prohibited at once), but nothing populates or consumes it yet — there's no Orchestrator on the other end. |

### Demo shortcuts specific to the Model Layer wiring

Same spirit as the existing "add assertion" shortcut (see
`periop_api/__init__.py`): the demo lets a client create a
`ConversationalHypothesis` or `RepairRequirement` directly via a form.
In the real system these would only ever come from governed extraction
over an actual conversation turn, mediated by the (unbuilt) Orchestrator
— never a client-facing "create hypothesis" endpoint. The causal-ECD
calculator and humour-check endpoints are genuinely standalone tools
(not shortcuts for something that will later be automatic), since they
don't correspond to a stored clinical object at all.

## Running the tests

```
pip install -e .
python3 -m pytest -q
```

126 tests currently pass: the model/reconciliation/gap-engine/closure/
eligibility unit tests, DB round-trip tests (skipped automatically if no
local Postgres is reachable), HTTP-level API tests for both the Phase 1
core and the v1.1 Model Layer endpoints, the Model Layer unit tests
(epistemic ladder, attention scoring, causal ECD/entropy, psychological
safety, humour policy, correction propagation), and the audit trail's
lineage-reconstruction and DB-level immutability tests. Where a test pins down a
*documented current limitation* (e.g. the engine not yet resolving a
stale-vs-current conflict via freshness, or a single-source assertion
staying UNVERIFIED rather than auto-confirming), its docstring says so —
it is not asserting that behaviour is correct, only that it's what the
code does right now.

## Running the demo locally

```
# 1. Postgres (adjust to however you run Postgres locally)
createdb periop_core
for f in db/migrations/*.sql; do psql -d periop_core -f "$f"; done

# 2. Backend
pip install -e .
PERIOP_DATABASE_URL="dbname=periop_core" python3 -m periop_api.main
# -> http://localhost:8000 (OpenAPI docs at /docs)

# 3. Frontend (separate terminal)
cd frontend
npm install
npm run dev
# -> http://localhost:5173, proxies /api to the backend above
```

## Running the demo as one container

```
docker build -t periop-demo .
docker run -p 8000:8000 -e PERIOP_DATABASE_URL="postgresql://user:pass@host/periop_core" periop-demo
# -> http://localhost:8000 serves both the API and the built frontend
```

As noted above, this exact `docker build` has not been run in this
environment (no Docker daemon available) — its runtime logic was
validated by simulation, not the Dockerfile syntax itself. Run it once
before relying on it, including for the Azure deployment path (`az acr
build` builds it remotely and doesn't need local Docker either, if that's
easier).

## Regenerating the doc exports

```
python3 scripts/export_dataset.py
```

## License / status

Working specification and prototype code — not a clinical guideline, not
validated, not approved for any patient-facing use. See
`docs/source/...Full_Project_and_Technical_Specification_v1.0.docx`
§"Document status".
