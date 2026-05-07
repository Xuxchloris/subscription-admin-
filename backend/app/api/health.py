from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.auth import require_admin
from app.core.config import get_settings
from app.db.session import get_db
from app.hermes.adapter import HermesCliAdapter
from app.models.job_metadata import JobMetadata, SyncStatus
from app.models.operation_result import OperationResult
from app.schemas.common import ok
from app.schemas.jobs import JobStatus

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("/hermes", dependencies=[Depends(require_admin)])
def hermes_health(db: Session = Depends(get_db)) -> dict:
    return ok(build_hermes_health(db))


def build_hermes_health(db: Session) -> dict:
    settings = get_settings()
    adapter = HermesCliAdapter()
    status_result, status = adapter.status()
    list_result, jobs = adapter.list_jobs()
    cron_dir = settings.hermes_home / "cron"
    output_dir = cron_dir / "output"
    last_result = (
        db.query(OperationResult).order_by(OperationResult.created_at.desc()).first()
    )
    metadata_problem_count = (
        db.query(JobMetadata)
        .filter(
            JobMetadata.sync_status.in_(
                [SyncStatus.sync_error.value, SyncStatus.last_operation_failed.value]
            )
        )
        .count()
    )
    unknown_job_count = (
        sum(1 for job in jobs if job.status == JobStatus.unknown) if list_result.ok else None
    )

    return {
        "cli": {
            "available": status_result.returncode != 127,
            "status_ok": status_result.ok,
            "returncode": status_result.returncode,
        },
        "gateway": {
            "running": bool(status.get("gateway_running", False)) if status_result.ok else False,
            "raw": status.get("raw", status_result.combined_output),
        },
        "cron_data": _readability(cron_dir),
        "output_dir": _readability(output_dir),
        "last_admin_operation": None
        if last_result is None
        else {
            "operation": last_result.operation,
            "hermes_job_id": last_result.hermes_job_id,
            "status": last_result.status,
            "stdout": last_result.stdout,
            "stderr": last_result.stderr,
            "created_at": last_result.created_at.isoformat(),
        },
        "job_counts": {
            "total": len(jobs) if list_result.ok else None,
            "active": sum(1 for job in jobs if job.status == JobStatus.active)
            if list_result.ok
            else None,
            "paused": sum(1 for job in jobs if job.status == JobStatus.paused)
            if list_result.ok
            else None,
            "sync_problems": unknown_job_count + metadata_problem_count
            if unknown_job_count is not None
            else metadata_problem_count,
        },
        "errors": [
            output
            for output in [status_result.combined_output, list_result.combined_output]
            if output and not (status_result.ok and list_result.ok)
        ],
    }


def _readability(path: Path) -> dict:
    exists = path.exists()
    is_dir = path.is_dir()
    readable = False
    error = ""
    if exists and is_dir:
        try:
            next(path.iterdir(), None)
            readable = True
        except OSError as exc:
            error = str(exc)
    return {
        "path": str(path),
        "exists": exists,
        "is_dir": is_dir,
        "readable": readable,
        "error": error,
    }
