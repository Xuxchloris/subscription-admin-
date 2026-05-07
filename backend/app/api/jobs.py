from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import require_admin
from app.db.session import get_db
from app.schemas.common import ok
from app.schemas.jobs import ContentGroupCreate, JobCreate, JobUpdate
from app.services.job_service import HermesOperationError, JobService

router = APIRouter(prefix="/api/jobs", tags=["jobs"], dependencies=[Depends(require_admin)])


def _service(db: Session) -> JobService:
    return JobService(db)


@router.get("")
def list_jobs(db: Session = Depends(get_db)) -> dict:
    try:
        return ok([job.model_dump() for job in _service(db).list_jobs()])
    except HermesOperationError as exc:
        raise HTTPException(status_code=502, detail=exc.error.model_dump()) from exc


@router.get("/content-groups")
def list_content_groups(db: Session = Depends(get_db)) -> dict:
    try:
        return ok([group.model_dump() for group in _service(db).list_content_groups()])
    except HermesOperationError as exc:
        raise HTTPException(status_code=502, detail=exc.error.model_dump()) from exc


@router.post("/content-groups")
def create_content_group(payload: ContentGroupCreate, db: Session = Depends(get_db)) -> dict:
    try:
        return ok(_service(db).create_content_group(payload).model_dump())
    except HermesOperationError as exc:
        raise HTTPException(status_code=502, detail=exc.error.model_dump()) from exc


@router.post("")
def create_job(payload: JobCreate, db: Session = Depends(get_db)) -> dict:
    try:
        return ok(_service(db).create_job(payload).model_dump())
    except HermesOperationError as exc:
        raise HTTPException(status_code=502, detail=exc.error.model_dump()) from exc


@router.get("/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        return ok(_service(db).get_job(job_id).model_dump())
    except HermesOperationError as exc:
        raise HTTPException(status_code=502, detail=exc.error.model_dump()) from exc


@router.put("/{job_id}")
def update_job(job_id: str, payload: JobUpdate, db: Session = Depends(get_db)) -> dict:
    try:
        return ok(_service(db).update_job(job_id, payload).model_dump())
    except HermesOperationError as exc:
        raise HTTPException(status_code=502, detail=exc.error.model_dump()) from exc


@router.post("/{job_id}/pause")
def pause_job(job_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        job = _service(db).pause_job(job_id)
        return ok(job.model_dump())
    except HermesOperationError as exc:
        raise HTTPException(status_code=502, detail=exc.error.model_dump()) from exc


@router.post("/{job_id}/resume")
def resume_job(job_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        job = _service(db).resume_job(job_id)
        return ok(job.model_dump())
    except HermesOperationError as exc:
        raise HTTPException(status_code=502, detail=exc.error.model_dump()) from exc


@router.post("/{job_id}/run")
def run_job(job_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        _service(db).run_job(job_id)
        return ok({"job_id": job_id})
    except HermesOperationError as exc:
        raise HTTPException(status_code=502, detail=exc.error.model_dump()) from exc


@router.delete("/{job_id}")
def delete_job(job_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        _service(db).delete_job(job_id)
        return ok({"job_id": job_id})
    except HermesOperationError as exc:
        raise HTTPException(status_code=502, detail=exc.error.model_dump()) from exc


@router.get("/{job_id}/runs")
def list_job_runs(job_id: str, db: Session = Depends(get_db)) -> dict:
    return ok({"job_id": job_id, "runs": _service(db).list_job_runs(job_id)})
