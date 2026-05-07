from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.auth import require_admin
from app.db.session import get_db
from app.schemas.common import ok
from app.schemas.jobs import ContentTemplateCreate, ContentTemplateUpdate
from app.services.template_service import TemplateService

router = APIRouter(prefix="/api/templates", tags=["templates"], dependencies=[Depends(require_admin)])


def _service(db: Session) -> TemplateService:
    return TemplateService(db)


@router.get("")
def list_templates(db: Session = Depends(get_db)) -> dict:
    return ok([template.model_dump() for template in _service(db).list_templates()])


@router.post("")
def create_template(payload: ContentTemplateCreate, db: Session = Depends(get_db)) -> dict:
    try:
        return ok(_service(db).create_template(payload).model_dump())
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "TEMPLATE_NAME_EXISTS",
                "message": "Content label name already exists.",
                "suggested_checks": ["Choose a unique content label name."],
            },
        ) from exc


@router.put("/{template_id}")
def update_template(template_id: int, payload: ContentTemplateUpdate, db: Session = Depends(get_db)) -> dict:
    try:
        template = _service(db).update_template(template_id, payload)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "TEMPLATE_NAME_EXISTS",
                "message": "Content label name already exists.",
                "suggested_checks": ["Choose a unique content label name."],
            },
        ) from exc
    if template is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "TEMPLATE_NOT_FOUND",
                "message": "Content label was not found.",
                "suggested_checks": ["Refresh the labels page and try again."],
            },
        )
    return ok(template.model_dump())


@router.delete("/{template_id}")
def delete_template(template_id: int, db: Session = Depends(get_db)) -> dict:
    if not _service(db).delete_template(template_id):
        raise HTTPException(
            status_code=404,
            detail={
                "code": "TEMPLATE_NOT_FOUND",
                "message": "Content label was not found.",
                "suggested_checks": ["Refresh the labels page and try again."],
            },
        )
    return ok({"id": template_id})
