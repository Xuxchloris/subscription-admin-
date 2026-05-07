from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.models.operation_result import OperationResult


class AuditService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        *,
        operation: str,
        status: str,
        hermes_job_id: str = "",
        owner_label: str = "",
        request_summary: str = "",
        command_category: str = "",
        error_message: str = "",
    ) -> AuditEvent:
        event = AuditEvent(
            operation=operation,
            hermes_job_id=hermes_job_id,
            owner_label=owner_label,
            request_summary=request_summary,
            command_category=command_category,
            status=status,
            error_message=error_message,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def record_operation_result(
        self,
        *,
        operation: str,
        status: str,
        hermes_job_id: str = "",
        stdout: str = "",
        stderr: str = "",
    ) -> OperationResult:
        result = OperationResult(
            operation=operation,
            hermes_job_id=hermes_job_id,
            status=status,
            stdout=stdout,
            stderr=stderr,
        )
        self.db.add(result)
        self.db.commit()
        self.db.refresh(result)
        return result
