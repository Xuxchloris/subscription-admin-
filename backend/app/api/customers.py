from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.auth import require_admin
from app.db.session import get_db
from app.schemas.common import ok
from app.schemas.subscriptions import CustomerCreate, CustomerUpdate
from app.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/api/customers", tags=["customers"], dependencies=[Depends(require_admin)])


def _service(db: Session) -> SubscriptionService:
    return SubscriptionService(db)


def _conflict(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "code": "CUSTOMER_NAME_EXISTS",
            "message": "Customer project name already exists.",
            "suggested_checks": ["Choose a unique customer project name."],
        },
    )


@router.get("")
def list_customers(db: Session = Depends(get_db)) -> dict:
    return ok([customer.model_dump() for customer in _service(db).list_customers()])


@router.post("")
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db)) -> dict:
    try:
        return ok(_service(db).create_customer(payload).model_dump())
    except IntegrityError as exc:
        db.rollback()
        raise _conflict(exc) from exc


@router.put("/{customer_id}")
def update_customer(customer_id: int, payload: CustomerUpdate, db: Session = Depends(get_db)) -> dict:
    try:
        customer = _service(db).update_customer(customer_id, payload)
    except IntegrityError as exc:
        db.rollback()
        raise _conflict(exc) from exc
    if customer is None:
        raise HTTPException(status_code=404, detail={"code": "CUSTOMER_NOT_FOUND", "message": "Customer not found."})
    return ok(customer.model_dump())


@router.delete("/{customer_id}")
def delete_customer(customer_id: int, db: Session = Depends(get_db)) -> dict:
    if not _service(db).delete_customer(customer_id):
        raise HTTPException(status_code=404, detail={"code": "CUSTOMER_NOT_FOUND", "message": "Customer not found."})
    return ok({"id": customer_id})
