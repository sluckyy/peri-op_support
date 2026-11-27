-- Extends audit_event_type (0003-0007) for red-flag escalations raised
-- from the clinician-approved escalation map, and for staff taking
-- ownership of / resolving the resulting tasks -- see
-- periop_core.escalation and periop_core.enums.AuditEventType.

ALTER TYPE audit_event_type ADD VALUE 'ESCALATION_RAISED';
ALTER TYPE audit_event_type ADD VALUE 'TASK_ACKNOWLEDGED';
ALTER TYPE audit_event_type ADD VALUE 'TASK_RESOLVED';
