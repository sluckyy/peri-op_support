-- Extends audit_event_type (0003/0004/0005) for the new ConflictReview
-- auto-creation and resolve endpoints -- see
-- periop_core.enums.AuditEventType.

ALTER TYPE audit_event_type ADD VALUE 'CONFLICT_REVIEW_CREATED';
ALTER TYPE audit_event_type ADD VALUE 'CONFLICT_REVIEW_RESOLVED';
