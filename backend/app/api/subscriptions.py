from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import require_admin
from app.db.session import get_db
from app.schemas.common import ok
from app.schemas.subscriptions import SubscriptionCreate, SubscriptionUpdate
from app.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"], dependencies=[Depends(require_admin)])


def _service(db: Session) -> SubscriptionService:
    return SubscriptionService(db)


@router.get("")
def list_subscriptions(
    search: str | None = None,
    status: str | None = None,
    customer_id: int | None = None,
    content_template_id: int | None = None,
    deliver_channel: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    return ok(
        [
            subscription.model_dump()
            for subscription in _service(db).list_subscriptions(
                search=search,
                status=status,
                customer_id=customer_id,
                content_template_id=content_template_id,
                deliver_channel=deliver_channel,
            )
        ]
    )


@router.post("")
def create_subscription(payload: SubscriptionCreate, db: Session = Depends(get_db)) -> dict:
    service = _service(db)
    validation_error = service.validate_subscription(payload)
    if validation_error:
        raise HTTPException(
            status_code=400,
            detail={"code": "SUBSCRIPTION_INVALID", "message": validation_error},
        )
    try:
        return ok(service.create_subscription(payload).model_dump())
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "SUBSCRIPTION_INVALID", "message": str(exc)},
        ) from exc


@router.put("/{subscription_id}")
def update_subscription(subscription_id: int, payload: SubscriptionUpdate, db: Session = Depends(get_db)) -> dict:
    service = _service(db)
    validation_error = service.validate_subscription(payload)
    if validation_error:
        raise HTTPException(
            status_code=400,
            detail={"code": "SUBSCRIPTION_INVALID", "message": validation_error},
        )
    try:
        subscription = service.update_subscription(subscription_id, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "SUBSCRIPTION_INVALID", "message": str(exc)},
        ) from exc
    if subscription is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "SUBSCRIPTION_NOT_FOUND", "message": "Subscription not found."},
        )
    return ok(subscription.model_dump())


@router.delete("/{subscription_id}")
def delete_subscription(subscription_id: int, db: Session = Depends(get_db)) -> dict:
    if not _service(db).delete_subscription(subscription_id):
        raise HTTPException(
            status_code=404,
            detail={"code": "SUBSCRIPTION_NOT_FOUND", "message": "Subscription not found."},
        )
    return ok({"id": subscription_id})


@router.get("/summary")
def dashboard_summary(db: Session = Depends(get_db)) -> dict:
    return ok(_service(db).dashboard_summary().model_dump())
