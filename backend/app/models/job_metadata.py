from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SyncStatus(str, Enum):
    synced = "synced"
    pending_confirmation = "pending_confirmation"
    sync_error = "sync_error"
    last_operation_failed = "last_operation_failed"
    expired = "expired"


class JobMetadata(Base):
    __tablename__ = "job_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hermes_job_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    content_id: Mapped[str] = mapped_column(String(120), default="", index=True)
    content_title: Mapped[str] = mapped_column(String(255), default="", index=True)
    content_template_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    content_template_name: Mapped[str] = mapped_column(String(255), default="", index=True)
    delivery_label: Mapped[str] = mapped_column(String(255), default="")
    owner_label: Mapped[str] = mapped_column(String(255), index=True)
    task_name: Mapped[str] = mapped_column(String(255), index=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_status: Mapped[SyncStatus] = mapped_column(String(40), default=SyncStatus.synced)
    last_error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
