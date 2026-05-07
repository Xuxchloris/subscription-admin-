from datetime import datetime

from pydantic import BaseModel


class AuditEventOut(BaseModel):
    id: int
    operation: str
    hermes_job_id: str
    owner_label: str
    status: str
    error_message: str
    created_at: datetime
