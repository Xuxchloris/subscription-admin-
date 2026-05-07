from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    operation: Mapped[str] = mapped_column(String(80), index=True)
    hermes_job_id: Mapped[str] = mapped_column(String(120), default="", index=True)
    owner_label: Mapped[str] = mapped_column(String(255), default="", index=True)
    request_summary: Mapped[str] = mapped_column(Text, default="")
    command_category: Mapped[str] = mapped_column(String(80), default="")
    status: Mapped[str] = mapped_column(String(40), index=True)
    error_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
