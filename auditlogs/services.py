from auditlogs.models import AuditLog


def create_audit_log(*, actor=None, employee=None, action, target_model, target_id, description="", changes=None, metadata=None, severity=AuditLog.Severity.INFO):
    return AuditLog.objects.create(
        actor=actor,
        employee=employee,
        action=action,
        severity=severity,
        target_model=target_model,
        target_id=str(target_id),
        description=description,
        changes=changes or {},
        metadata=metadata or {},
    )
