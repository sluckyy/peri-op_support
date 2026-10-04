-- Extends audit_event_type (0003_audit_trail.sql, 0004_audit_trail_model_
-- layer_events.sql) for the new CausalHypothesis create/status-change
-- endpoints -- see periop_core.enums.AuditEventType.

ALTER TYPE audit_event_type ADD VALUE 'CAUSAL_HYPOTHESIS_CREATED';
ALTER TYPE audit_event_type ADD VALUE 'CAUSAL_HYPOTHESIS_STATUS_CHANGED';
