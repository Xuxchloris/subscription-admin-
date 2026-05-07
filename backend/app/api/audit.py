from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.auth import require_admin
from app.db.session import get_db
from app.models.audit import AuditEvent
from app.schemas.common import ok

router = APIRouter(prefix="/api/audit", tags=["audit"], dependencies=[Depends(require_admin)])


@router.get("")
def list_audit(db: Session = Depends(get_db)) -> dict:
    events = db.query(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(100).all()
    return ok(
        [
            {
                "id": event.id,
                "operation": event.operation,
                "hermes_job_id": event.hermes_job_id,
                "owner_label": event.owner_label,
                "status": event.status,
                "error_message": event.error_message,
                "created_at": event.created_at.isoformat(),
            }
            for event in events
        ]
    )
