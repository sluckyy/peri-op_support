-- Extends audit_event_type (0003_audit_trail.sql) to cover the v1.1
-- Model Layer mutations -- see periop_core.enums.AuditEventType and the
-- periop_api endpoints that now call append_event for hypotheses,
-- propositions, obligations, contradictions, uncertainties, repairs and
-- psychological-safety signals.
--
-- ALTER TYPE ... ADD VALUE cannot run inside the same transaction as a
-- later statement that uses the new value, but it's fine as its own
-- migration file applied before anything references these values.

ALTER TYPE audit_event_type ADD VALUE 'HYPOTHESIS_CREATED';
ALTER TYPE audit_event_type ADD VALUE 'HYPOTHESIS_PROMOTED';
ALTER TYPE audit_event_type ADD VALUE 'PROPOSITION_CORRECTED';
ALTER TYPE audit_event_type ADD VALUE 'OBLIGATION_CREATED';
ALTER TYPE audit_event_type ADD VALUE 'CONTRADICTION_LOGGED';
ALTER TYPE audit_event_type ADD VALUE 'UNCERTAINTY_LOGGED';
ALTER TYPE audit_event_type ADD VALUE 'REPAIR_CREATED';
ALTER TYPE audit_event_type ADD VALUE 'REPAIR_RESOLVED';
ALTER TYPE audit_event_type ADD VALUE 'PSYCHOLOGICAL_SAFETY_SIGNAL_APPLIED';
