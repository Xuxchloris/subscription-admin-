from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.hermes.adapter import HermesCliAdapter, HermesCommandResult
from app.models.job_metadata import JobMetadata, SyncStatus
from app.models.operation_result import OperationResult
from app.schemas.common import ApiError
from app.schemas.jobs import ContentDelivery, ContentGroup, ContentGroupCreate, HermesJob, JobCreate, JobStatus, JobUpdate
from app.services.audit_service import AuditService


class HermesOperationError(Exception):
    def __init__(self, error: ApiError) -> None:
        super().__init__(error.message)
        self.error = error


_operation_lock = Lock()
_active_operations: set[str] = set()


class JobService:
    def __init__(
        self,
        db: Session | None,
        hermes: HermesCliAdapter | None = None,
        hermes_home: Path | None = None,
    ) -> None:
        self.db = db
        self.hermes = hermes or HermesCliAdapter()
        self.hermes_home = hermes_home or get_settings().hermes_home
        self.audit = AuditService(db) if db is not None else None
        self._active_operations = _active_operations

    def _failure(
        self,
        *,
        operation: str,
        message: str,
        result: HermesCommandResult | None = None,
    ) -> HermesOperationError:
        hermes_output = result.combined_output if result else ""
        return HermesOperationError(
            ApiError(
                code="HERMES_OPERATION_FAILED",
                message=message,
                operation=operation,
                hermes_output=hermes_output,
                suggested_checks=[
                    "Check that Hermes CLI is installed and available to the FastAPI process.",
                    "Check that Hermes gateway is running.",
                    "Check that the schedule and delivery target are valid.",
                    "Check file permissions for ~/.hermes/cron.",
                ],
            )
        )

    def _in_progress_failure(self, job_id: str, operation: str) -> HermesOperationError:
        return HermesOperationError(
            ApiError(
                code="HERMES_OPERATION_IN_PROGRESS",
                message="A Hermes operation is already running for this task.",
                operation=operation,
                hermes_output="",
                suggested_checks=["Wait for the current operation to finish, then retry."],
            )
        )

    def _begin_job_operation(self, job_id: str, operation: str) -> None:
        with _operation_lock:
            if job_id in _active_operations:
                raise self._in_progress_failure(job_id, operation)
            _active_operations.add(job_id)

    def _end_job_operation(self, job_id: str) -> None:
        with _operation_lock:
            _active_operations.discard(job_id)

    def _sync_status_value(self, status: SyncStatus | str) -> str:
        return status.value if isinstance(status, SyncStatus) else str(status)

    def _utc_now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _iso(self, value: datetime | None) -> str | None:
        return value.isoformat() if value else None

    def _expiry_fields(self, metadata: JobMetadata | None) -> dict[str, Any]:
        if metadata is None or metadata.expires_at is None:
            return {
                "duration_days": None,
                "starts_at": None,
                "expires_at": None,
                "expired_at": None,
                "expiry_status": "permanent",
                "seconds_remaining": None,
            }
        now = self._utc_now()
        expires_at = metadata.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        remaining = int((expires_at - now).total_seconds())
        if metadata.expired_at is not None or remaining <= 0:
            status = "expired"
            seconds_remaining = 0
        elif remaining <= 86_400:
            status = "expires_today"
            seconds_remaining = remaining
        else:
            status = "active"
            seconds_remaining = remaining
        return {
            "duration_days": metadata.duration_days,
            "starts_at": self._iso(metadata.starts_at),
            "expires_at": self._iso(metadata.expires_at),
            "expired_at": self._iso(metadata.expired_at),
            "expiry_status": status,
            "seconds_remaining": seconds_remaining,
        }

    def _apply_expired_jobs(self, jobs: list[HermesJob], metadata_by_job_id: dict[str, JobMetadata]) -> None:
        if self.db is None:
            return
        now = self._utc_now()
        changed = False
        for job in jobs:
            metadata = metadata_by_job_id.get(job.id)
            if metadata is None or metadata.expires_at is None or metadata.expired_at is not None:
                continue
            expires_at = metadata.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at > now:
                continue
            if job.status == JobStatus.active:
                self.hermes.pause_job(job.id)
            metadata.sync_status = SyncStatus.expired
            metadata.expired_at = now
            metadata.last_error = "Content delivery expired and was paused."
            changed = True
            if self.audit is not None:
                self.audit.record(
                    operation="expire_job",
                    status="success",
                    hermes_job_id=job.id,
                    owner_label=metadata.owner_label,
                    request_summary=metadata.task_name,
                    command_category="hermes cron pause",
                )
        if changed:
            self.db.commit()

    def _record_failed_operation(
        self,
        *,
        operation: str,
        message: str,
        result: HermesCommandResult | None = None,
        hermes_job_id: str = "",
        owner_label: str = "",
        request_summary: str = "",
        command_category: str = "",
    ) -> None:
        if self.audit is None:
            return
        self.audit.record_operation_result(
            operation=operation,
            status="failed",
            hermes_job_id=hermes_job_id,
            stdout=result.stdout if result else "",
            stderr=result.stderr if result else message,
        )
        self.audit.record(
            operation=operation,
            status="failed",
            hermes_job_id=hermes_job_id,
            owner_label=owner_label,
            request_summary=request_summary,
            command_category=command_category,
            error_message=message,
        )

    def _raise_failure(
        self,
        *,
        operation: str,
        message: str,
        result: HermesCommandResult | None = None,
        hermes_job_id: str = "",
        owner_label: str = "",
        request_summary: str = "",
        command_category: str = "",
    ) -> HermesOperationError:
        self._record_failed_operation(
            operation=operation,
            message=message,
            result=result,
            hermes_job_id=hermes_job_id,
            owner_label=owner_label,
            request_summary=request_summary,
            command_category=command_category,
        )
        return self._failure(operation=operation, message=message, result=result)

    def _find_confirmed_job(
        self,
        *,
        expected_name: str,
        before_ids: set[str],
        operation: str,
        owner_label: str = "",
        request_summary: str = "",
        command_category: str = "",
    ) -> HermesJob | None:
        list_result, jobs = self.hermes.list_jobs()
        if not list_result.ok:
            raise self._raise_failure(
                operation=operation,
                message="Hermes accepted the operation, but job confirmation failed.",
                result=list_result,
                owner_label=owner_label,
                request_summary=request_summary,
                command_category=command_category,
            )
        for job in jobs:
            if job.id not in before_ids and (job.name == expected_name or not job.name):
                return job
        for job in jobs:
            if job.id not in before_ids:
                return job
        return None

    def _last_operation_result(self, job_id: str) -> dict[str, Any] | None:
        if self.db is None:
            return None
        result = (
            self.db.query(OperationResult)
            .filter_by(hermes_job_id=job_id)
            .order_by(OperationResult.created_at.desc())
            .first()
        )
        if result is None:
            return None
        return {
            "operation": result.operation,
            "status": result.status,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "created_at": result.created_at.isoformat(),
        }

    def _merge_metadata(self, jobs: list[HermesJob]) -> list[HermesJob]:
        if self.db is None:
            return [self._job_with_default_display_fields(job) for job in jobs]
        metadata_items = self.db.query(JobMetadata).all()
        metadata_by_job_id = {item.hermes_job_id: item for item in metadata_items}
        hermes_ids = {job.id for job in jobs}
        self._apply_expired_jobs(jobs, metadata_by_job_id)

        changed = False
        for metadata in metadata_items:
            if metadata.hermes_job_id not in hermes_ids:
                metadata.sync_status = SyncStatus.sync_error
                metadata.last_error = "Hermes job missing from source of truth."
                changed = True
        if changed:
            self.db.commit()

        merged: list[HermesJob] = []
        for job in jobs:
            metadata = metadata_by_job_id.get(job.id)
            if metadata is None:
                merged.append(self._job_with_default_display_fields(job))
                continue
            merged.append(
                job.model_copy(
                    update={
                        "owner_label": metadata.owner_label,
                        "task_name": metadata.task_name,
                        "notes": metadata.notes,
                        "content_id": metadata.content_id or metadata.hermes_job_id,
                        "content_title": metadata.content_title or metadata.task_name,
                        "content_template_id": metadata.content_template_id,
                        "content_template_name": metadata.content_template_name,
                        "delivery_label": metadata.delivery_label,
                        "sync_status": self._sync_status_value(metadata.sync_status),
                        "last_error": metadata.last_error,
                        "last_run_result": self._last_operation_result(job.id),
                        **self._expiry_fields(metadata),
                    }
                )
            )
        return merged

    def _job_with_default_display_fields(self, job: HermesJob) -> HermesJob:
        return job.model_copy(
            update={
                "task_name": job.task_name or job.name,
                "content_id": job.content_id or job.id,
                "content_title": job.content_title or job.task_name or job.name,
            }
        )

    def _content_id_for_metadata(self, metadata: JobMetadata | None, job: HermesJob) -> str:
        if metadata and metadata.content_id:
            return metadata.content_id
        return job.id

    def _content_title_for_metadata(self, metadata: JobMetadata | None, job: HermesJob) -> str:
        if metadata and metadata.content_title:
            return metadata.content_title
        if metadata and metadata.task_name:
            return metadata.task_name
        return job.task_name or job.name or job.id

    def _content_expiry_for_group(self, metadata: JobMetadata | None) -> dict[str, Any]:
        return self._expiry_fields(metadata)

    def _set_metadata_operation_failed(self, job_id: str, message: str) -> None:
        if self.db is None:
            return
        metadata = self.db.query(JobMetadata).filter_by(hermes_job_id=job_id).one_or_none()
        if metadata:
            metadata.sync_status = SyncStatus.last_operation_failed
            metadata.last_error = message
            self.db.commit()

    def _find_job(self, job_id: str) -> HermesJob | None:
        list_result, jobs = self.hermes.list_jobs()
        if not list_result.ok:
            raise self._raise_failure(
                operation="list_jobs",
                message="Hermes operation could not be confirmed.",
                result=list_result,
                hermes_job_id=job_id,
                command_category="hermes cron list",
            )
        return next((job for job in jobs if job.id == job_id), None)

    def _find_job_for_operation(
        self,
        *,
        job_id: str,
        operation: str,
        message: str,
        owner_label: str = "",
        request_summary: str = "",
        command_category: str = "",
    ) -> HermesJob | None:
        list_result, jobs = self.hermes.list_jobs()
        if not list_result.ok:
            raise self._raise_failure(
                operation=operation,
                message=message,
                result=list_result,
                hermes_job_id=job_id,
                owner_label=owner_label,
                request_summary=request_summary,
                command_category=command_category,
            )
        return next((job for job in jobs if job.id == job_id), None)

    def _confirm_job_fields(self, confirmed: HermesJob, payload: JobUpdate) -> bool:
        if confirmed.status == JobStatus.unknown:
            return False
        raw = confirmed.raw if isinstance(confirmed.raw, dict) else {}
        expected = {
            "name": payload.task_name,
            "task_name": payload.task_name,
            "prompt": payload.prompt,
            "schedule": payload.schedule,
            "deliver": payload.deliver,
        }
        matched_any_field = False
        for field, expected_value in expected.items():
            if field not in raw:
                continue
            matched_any_field = True
            if str(raw[field]) != str(expected_value):
                return False
        if "skills" in raw:
            matched_any_field = True
            actual_skills = raw["skills"] if isinstance(raw["skills"], list) else []
            if actual_skills != payload.skills:
                return False
        return matched_any_field or confirmed.id != ""

    def create_job(self, payload: JobCreate) -> HermesJob:
        before_result, before_jobs = self.hermes.list_jobs()
        if not before_result.ok:
            raise self._raise_failure(
                operation="create_job",
                message="Could not read Hermes jobs before creation.",
                result=before_result,
                owner_label=payload.owner_label,
                request_summary=payload.task_name,
                command_category="hermes cron list",
            )

        before_ids = {job.id for job in before_jobs}
        create_result = self.hermes.create_job(payload)
        if not create_result.ok:
            self._record_failed_operation(
                operation="create_job",
                owner_label=payload.owner_label,
                request_summary=payload.task_name,
                command_category="hermes cron create",
                message="Failed to deploy task to Hermes.",
                result=create_result,
            )
            raise self._failure(
                operation="create_job",
                message="Failed to deploy task to Hermes.",
                result=create_result,
            )

        confirmed = self._find_confirmed_job(
            expected_name=payload.task_name,
            before_ids=before_ids,
            operation="create_job",
            owner_label=payload.owner_label,
            request_summary=payload.task_name,
            command_category="hermes cron create",
        )
        if confirmed is None:
            raise self._raise_failure(
                operation="create_job",
                message="Hermes command succeeded, but the new task could not be confirmed.",
                result=create_result,
                owner_label=payload.owner_label,
                request_summary=payload.task_name,
                command_category="hermes cron create",
            )

        metadata = JobMetadata(
            hermes_job_id=confirmed.id,
            content_id=confirmed.id,
            content_title=payload.task_name,
            delivery_label=payload.deliver,
            owner_label=payload.owner_label,
            task_name=payload.task_name,
            notes=payload.notes,
            sync_status=SyncStatus.synced,
        )
        self.db.add(metadata)
        self.db.commit()
        if self.audit is not None:
            self.audit.record_operation_result(
                operation="create_job",
                status="success",
                hermes_job_id=confirmed.id,
                stdout=create_result.stdout,
                stderr=create_result.stderr,
            )
            self.audit.record(
                operation="create_job",
                status="success",
                hermes_job_id=confirmed.id,
                owner_label=payload.owner_label,
                request_summary=payload.task_name,
                command_category="hermes cron create",
            )
        return self._merge_metadata([confirmed])[0]

    def list_jobs(self) -> list[HermesJob]:
        result, jobs = self.hermes.list_jobs()
        if not result.ok:
            raise self._raise_failure(
                operation="list_jobs",
                message="Failed to read Hermes jobs.",
                result=result,
                command_category="hermes cron list",
            )
        return self._merge_metadata(jobs)

    def list_content_groups(self) -> list[ContentGroup]:
        jobs = self.list_jobs()
        groups: dict[str, ContentGroup] = {}
        metadata_by_job_id: dict[str, JobMetadata] = {}
        if self.db is not None:
            metadata_by_job_id = {
                metadata.hermes_job_id: metadata for metadata in self.db.query(JobMetadata).all()
            }

        for job in jobs:
            metadata = metadata_by_job_id.get(job.id)
            content_id = self._content_id_for_metadata(metadata, job)
            title = self._content_title_for_metadata(metadata, job)
            if content_id not in groups:
                expiry = self._content_expiry_for_group(metadata)
                groups[content_id] = ContentGroup(
                    content_id=content_id,
                    title=title,
                    owner_label=job.owner_label,
                    prompt=job.prompt,
                    skills=job.skills,
                    notes=job.notes,
                    content_template_id=metadata.content_template_id if metadata else job.content_template_id,
                    content_template_name=metadata.content_template_name if metadata else job.content_template_name,
                    duration_days=expiry["duration_days"],
                    expires_at=expiry["expires_at"],
                    expiry_status=expiry["expiry_status"],
                    seconds_remaining=expiry["seconds_remaining"],
                    deliveries=[],
                )
            delivery_expiry = self._expiry_fields(metadata)
            groups[content_id].deliveries.append(
                ContentDelivery(
                    job_id=job.id,
                    label=job.delivery_label or job.deliver,
                    schedule=job.schedule,
                    deliver=job.deliver,
                    status=job.status,
                    next_run_at=job.next_run_at,
                    sync_status=job.sync_status,
                    last_error=job.last_error,
                    last_run_result=job.last_run_result,
                    expires_at=delivery_expiry["expires_at"],
                    expired_at=delivery_expiry["expired_at"],
                    expiry_status=delivery_expiry["expiry_status"],
                    seconds_remaining=delivery_expiry["seconds_remaining"],
                )
            )

        return sorted(groups.values(), key=lambda group: group.title.lower())

    def create_content_group(self, payload: ContentGroupCreate | dict[str, Any]) -> ContentGroup:
        parsed = payload if isinstance(payload, ContentGroupCreate) else ContentGroupCreate.model_validate(payload)
        if not parsed.deliveries:
            raise self._failure(operation="create_content_group", message="At least one delivery is required.")

        content_id = f"content-{uuid4().hex[:12]}"
        starts_at = self._utc_now()
        expires_at = (
            starts_at + timedelta(days=parsed.duration_days)
            if parsed.duration_days is not None and parsed.duration_days > 0
            else None
        )
        created_jobs: list[HermesJob] = []
        for delivery in parsed.deliveries:
            job_payload = JobCreate(
                owner_label=parsed.owner_label,
                task_name=parsed.title,
                prompt=parsed.prompt,
                schedule=delivery.schedule,
                deliver=delivery.deliver,
                skills=parsed.skills,
                notes=parsed.notes,
            )
            created = self.create_job(job_payload)
            metadata = self.db.query(JobMetadata).filter_by(hermes_job_id=created.id).one_or_none() if self.db else None
            if metadata:
                metadata.content_id = content_id
                metadata.content_title = parsed.title
                metadata.delivery_label = delivery.label or delivery.deliver
                metadata.owner_label = parsed.owner_label
                metadata.task_name = parsed.title
                metadata.notes = parsed.notes
                metadata.content_template_id = parsed.content_template_id
                metadata.content_template_name = parsed.content_template_name
                metadata.duration_days = parsed.duration_days
                metadata.starts_at = starts_at
                metadata.expires_at = expires_at
                self.db.commit()
            created_jobs.append(
                created.model_copy(
                    update={
                        "content_id": content_id,
                        "content_title": parsed.title,
                        "delivery_label": delivery.label or delivery.deliver,
                        "content_template_id": parsed.content_template_id,
                        "content_template_name": parsed.content_template_name,
                        "duration_days": parsed.duration_days,
                        "starts_at": self._iso(starts_at),
                        "expires_at": self._iso(expires_at),
                    }
                )
            )

        return ContentGroup(
            content_id=content_id,
            title=parsed.title,
            owner_label=parsed.owner_label,
            prompt=parsed.prompt,
            skills=parsed.skills,
            notes=parsed.notes,
            content_template_id=parsed.content_template_id,
            content_template_name=parsed.content_template_name,
            duration_days=parsed.duration_days,
            expires_at=self._iso(expires_at),
            expiry_status="active" if expires_at else "permanent",
            seconds_remaining=int((expires_at - starts_at).total_seconds()) if expires_at else None,
            deliveries=[
                ContentDelivery(
                    job_id=job.id,
                    label=job.delivery_label or job.deliver,
                    schedule=job.schedule,
                    deliver=job.deliver,
                    status=job.status,
                    next_run_at=job.next_run_at,
                    sync_status=job.sync_status,
                    last_error=job.last_error,
                    last_run_result=job.last_run_result,
                    expires_at=job.expires_at,
                    expiry_status="active" if expires_at else "permanent",
                    seconds_remaining=int((expires_at - starts_at).total_seconds()) if expires_at else None,
                )
                for job in created_jobs
            ],
        )

    def get_job(self, job_id: str) -> HermesJob:
        job = self._find_job(job_id)
        if job is None:
            raise self._raise_failure(
                operation="get_job",
                message="Hermes task could not be found.",
                hermes_job_id=job_id,
                command_category="hermes cron list",
            )
        return self._merge_metadata([job])[0]

    def update_job(self, job_id: str, payload: JobUpdate) -> HermesJob:
        self._begin_job_operation(job_id, "update_job")
        try:
            result = self.hermes.edit_job(job_id, payload)
            if not result.ok:
                self._set_metadata_operation_failed(job_id, "Failed to update Hermes task.")
                raise self._raise_failure(
                    operation="update_job",
                    message="Failed to update Hermes task.",
                    result=result,
                    hermes_job_id=job_id,
                    owner_label=payload.owner_label,
                    request_summary=payload.task_name,
                    command_category="hermes cron edit",
                )
            confirmed = self._find_job_for_operation(
                job_id=job_id,
                operation="update_job",
                message="Updated task could not be confirmed.",
                owner_label=payload.owner_label,
                request_summary=payload.task_name,
                command_category="hermes cron edit",
            )
            if confirmed is None:
                self._set_metadata_operation_failed(job_id, "Updated task is missing from Hermes.")
                raise self._raise_failure(
                    operation="update_job",
                    message="Updated task is missing from Hermes.",
                    result=result,
                    hermes_job_id=job_id,
                    owner_label=payload.owner_label,
                    request_summary=payload.task_name,
                    command_category="hermes cron edit",
                )
            if not self._confirm_job_fields(confirmed, payload):
                self._set_metadata_operation_failed(job_id, "Updated task could not be confirmed.")
                raise self._raise_failure(
                    operation="update_job",
                    message="Updated task could not be confirmed.",
                    result=result,
                    hermes_job_id=job_id,
                    owner_label=payload.owner_label,
                    request_summary=payload.task_name,
                    command_category="hermes cron edit",
                )
            metadata = self.db.query(JobMetadata).filter_by(hermes_job_id=job_id).one_or_none()
            if metadata:
                metadata.owner_label = payload.owner_label
                metadata.task_name = payload.task_name
                metadata.notes = payload.notes
                metadata.sync_status = SyncStatus.synced
                metadata.last_error = ""
                self.db.commit()
            if self.audit is not None:
                self.audit.record_operation_result(
                    operation="update_job",
                    status="success",
                    hermes_job_id=job_id,
                    stdout=result.stdout,
                    stderr=result.stderr,
                )
                self.audit.record(
                    operation="update_job",
                    status="success",
                    hermes_job_id=job_id,
                    owner_label=payload.owner_label,
                    request_summary=payload.task_name,
                    command_category="hermes cron edit",
                )
            return self._merge_metadata([confirmed])[0]
        finally:
            self._end_job_operation(job_id)

    def pause_job(self, job_id: str) -> HermesJob:
        self._begin_job_operation(job_id, "pause_job")
        try:
            result = self.hermes.pause_job(job_id)
            if not result.ok:
                self._set_metadata_operation_failed(job_id, "Failed to pause Hermes task.")
                raise self._raise_failure(
                    operation="pause_job",
                    message="Failed to pause Hermes task.",
                    result=result,
                    hermes_job_id=job_id,
                    command_category="hermes cron pause",
                )
            confirmed = self._find_job_for_operation(
                job_id=job_id,
                operation="pause_job",
                message="Paused task could not be confirmed.",
                command_category="hermes cron pause",
            )
            if confirmed is None or confirmed.status != JobStatus.paused:
                self._set_metadata_operation_failed(job_id, "Paused task could not be confirmed.")
                raise self._raise_failure(
                    operation="pause_job",
                    message="Paused task could not be confirmed.",
                    result=result,
                    hermes_job_id=job_id,
                    command_category="hermes cron pause",
                )
            if self.audit is not None:
                self.audit.record_operation_result(
                    operation="pause_job",
                    status="success",
                    hermes_job_id=job_id,
                    stdout=result.stdout,
                    stderr=result.stderr,
                )
                self.audit.record(
                    operation="pause_job",
                    status="success",
                    hermes_job_id=job_id,
                    command_category="hermes cron pause",
                )
            return self._merge_metadata([confirmed])[0]
        finally:
            self._end_job_operation(job_id)

    def resume_job(self, job_id: str) -> HermesJob:
        self._begin_job_operation(job_id, "resume_job")
        try:
            result = self.hermes.resume_job(job_id)
            if not result.ok:
                self._set_metadata_operation_failed(job_id, "Failed to resume Hermes task.")
                raise self._raise_failure(
                    operation="resume_job",
                    message="Failed to resume Hermes task.",
                    result=result,
                    hermes_job_id=job_id,
                    command_category="hermes cron resume",
                )
            confirmed = self._find_job_for_operation(
                job_id=job_id,
                operation="resume_job",
                message="Resumed task could not be confirmed.",
                command_category="hermes cron resume",
            )
            if confirmed is None or confirmed.status != JobStatus.active:
                self._set_metadata_operation_failed(job_id, "Resumed task could not be confirmed.")
                raise self._raise_failure(
                    operation="resume_job",
                    message="Resumed task could not be confirmed.",
                    result=result,
                    hermes_job_id=job_id,
                    command_category="hermes cron resume",
                )
            if self.audit is not None:
                self.audit.record_operation_result(
                    operation="resume_job",
                    status="success",
                    hermes_job_id=job_id,
                    stdout=result.stdout,
                    stderr=result.stderr,
                )
                self.audit.record(
                    operation="resume_job",
                    status="success",
                    hermes_job_id=job_id,
                    command_category="hermes cron resume",
                )
            return self._merge_metadata([confirmed])[0]
        finally:
            self._end_job_operation(job_id)

    def run_job(self, job_id: str) -> None:
        self._begin_job_operation(job_id, "run_job")
        try:
            result = self.hermes.run_job(job_id)
            if not result.ok:
                self._set_metadata_operation_failed(job_id, "Failed to trigger Hermes task.")
                raise self._raise_failure(
                    operation="run_job",
                    message="Failed to trigger Hermes task.",
                    result=result,
                    hermes_job_id=job_id,
                    command_category="hermes cron run",
                )
            if self.audit is not None:
                self.audit.record_operation_result(
                    operation="run_job",
                    status="success",
                    hermes_job_id=job_id,
                    stdout=result.stdout,
                    stderr=result.stderr,
                )
                self.audit.record(
                    operation="run_job",
                    status="success",
                    hermes_job_id=job_id,
                    command_category="hermes cron run",
                )
        finally:
            self._end_job_operation(job_id)

    def delete_job(self, job_id: str) -> None:
        self._begin_job_operation(job_id, "delete_job")
        try:
            result = self.hermes.remove_job(job_id)
            if not result.ok:
                self._set_metadata_operation_failed(job_id, "Failed to delete Hermes task.")
                raise self._raise_failure(
                    operation="delete_job",
                    message="Failed to delete Hermes task.",
                    result=result,
                    hermes_job_id=job_id,
                    command_category="hermes cron remove",
                )
            confirmed = self._find_job_for_operation(
                job_id=job_id,
                operation="delete_job",
                message="Deleted task could not be confirmed.",
                command_category="hermes cron remove",
            )
            if confirmed is not None:
                self._set_metadata_operation_failed(job_id, "Deleted task still appears in Hermes.")
                raise self._raise_failure(
                    operation="delete_job",
                    message="Deleted task still appears in Hermes.",
                    result=result,
                    hermes_job_id=job_id,
                    command_category="hermes cron remove",
                )
            metadata = self.db.query(JobMetadata).filter_by(hermes_job_id=job_id).one_or_none()
            if metadata:
                self.db.delete(metadata)
                self.db.commit()
            if self.audit is not None:
                self.audit.record_operation_result(
                    operation="delete_job",
                    status="success",
                    hermes_job_id=job_id,
                    stdout=result.stdout,
                    stderr=result.stderr,
                )
                self.audit.record(
                    operation="delete_job",
                    status="success",
                    hermes_job_id=job_id,
                    command_category="hermes cron remove",
                )
        finally:
            self._end_job_operation(job_id)

    def list_job_runs(self, job_id: str, limit: int = 20) -> list[dict[str, Any]]:
        output_dir = self.hermes_home / "cron" / "output"
        if not output_dir.exists() or not output_dir.is_dir():
            return []

        text_suffixes = {".log", ".txt", ".out", ".err", ".md"}
        candidates: list[Path] = []
        for path in output_dir.iterdir():
            if not path.is_file() or path.suffix.lower() not in text_suffixes:
                continue
            if job_id not in path.name:
                continue
            candidates.append(path)

        runs: list[dict[str, Any]] = []
        for path in sorted(candidates, key=lambda item: item.stat().st_mtime, reverse=True)[:limit]:
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                content = f"Could not read output file: {exc}"
            stat = path.stat()
            runs.append(
                {
                    "file_name": path.name,
                    "path": str(path),
                    "size_bytes": stat.st_size,
                    "modified_at": stat.st_mtime,
                    "content": content,
                }
            )
        return runs
