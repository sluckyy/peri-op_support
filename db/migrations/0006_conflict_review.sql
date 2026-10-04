-- A durable, never-recomputed log of real patient-vs-record disagreements
-- and how a clinician resolved them -- see periop_core.models.ConflictReview's
-- docstring for why this cannot share `conflict`'s persistence
-- (0001_init.sql's `conflict` table is deleted and reinserted wholesale on
-- every reconciliation pass; a clinician's decision stored there would be
-- silently wiped out the next time anyone loaded the session summary).
--
-- Reuses `contradiction_status` (0002_model_layer.sql) rather than adding
-- a near-duplicate enum: OPEN/RECONCILED/ESCALATED is the same lifecycle
-- question whether it's a conversational Contradiction or a Clinical
-- State Conflict under review.
--
-- `review_id` is NOT server-generated (no DEFAULT): periop_api computes
-- it deterministically from the session and the disagreeing assertion
-- set, so re-detecting the same disagreement finds the existing row
-- instead of creating a duplicate.

CREATE TABLE conflict_review (
    review_id       UUID PRIMARY KEY,
    session_id      UUID NOT NULL REFERENCES session (session_id),
    conflict_id     UUID NOT NULL,
    concept_json    JSONB NOT NULL,
    sides_json      JSONB NOT NULL,
    status          contradiction_status NOT NULL DEFAULT 'OPEN',
    resolution_json JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT conflict_review_resolution_required_once_decided
        CHECK (status = 'OPEN' OR resolution_json IS NOT NULL)
);
CREATE INDEX idx_conflict_review_session_id ON conflict_review (session_id, created_at);
