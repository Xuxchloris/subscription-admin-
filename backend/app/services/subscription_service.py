from datetime import date, datetime, timedelta

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.content_template import ContentTemplate
from app.models.customer import Customer as CustomerModel
from app.models.subscription import Subscription as SubscriptionModel
from app.schemas.subscriptions import (
    Customer,
    CustomerCreate,
    CustomerUpdate,
    DashboardSummary,
    Subscription,
    SubscriptionCreate,
    SubscriptionUpdate,
)


class SubscriptionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _customer_schema(self, customer: CustomerModel) -> Customer:
        return Customer(
            id=customer.id,
            name=customer.name,
            contact=customer.contact,
            status=customer.status,
            notes=customer.notes,
            created_at=customer.created_at.isoformat() if customer.created_at else None,
            updated_at=customer.updated_at.isoformat() if customer.updated_at else None,
        )

    def _expiry(self, end_date: date | None) -> tuple[str, int | None]:
        if end_date is None:
            return "permanent", None
        remaining = (end_date - date.today()).days
        if remaining < 0:
            return "expired", 0
        if remaining <= 7:
            return "expiring_soon", remaining
        return "active", remaining

    def _subscription_schema(self, subscription: SubscriptionModel) -> Subscription:
        expiry_status, days_remaining = self._expiry(subscription.end_date)
        status = "expired" if expiry_status == "expired" else subscription.status
        return Subscription(
            id=subscription.id,
            customer_id=subscription.customer_id,
            customer_name=subscription.customer_name,
            content_template_id=subscription.content_template_id,
            content_template_name=subscription.content_template_name,
            deliver_channel=subscription.deliver_channel,
            deliver_address=subscription.deliver_address,
            frequency=subscription.frequency,
            start_date=subscription.start_date,
            end_date=subscription.end_date,
            duration_days=subscription.duration_days,
            status=status,
            expiry_status=expiry_status,
            days_remaining=days_remaining,
            notes=subscription.notes,
            created_at=subscription.created_at.isoformat() if subscription.created_at else None,
            updated_at=subscription.updated_at.isoformat() if subscription.updated_at else None,
        )

    def list_customers(self) -> list[Customer]:
        customers = self.db.query(CustomerModel).order_by(CustomerModel.name.asc()).all()
        return [self._customer_schema(customer) for customer in customers]

    def create_customer(self, payload: CustomerCreate) -> Customer:
        customer = CustomerModel(
            name=payload.name.strip(),
            contact=payload.contact,
            status=payload.status,
            notes=payload.notes,
        )
        self.db.add(customer)
        self.db.commit()
        self.db.refresh(customer)
        return self._customer_schema(customer)

    def update_customer(self, customer_id: int, payload: CustomerUpdate) -> Customer | None:
        customer = self.db.get(CustomerModel, customer_id)
        if customer is None:
            return None
        customer.name = payload.name.strip()
        customer.contact = payload.contact
        customer.status = payload.status
        customer.notes = payload.notes
        for subscription in self.db.query(SubscriptionModel).filter_by(customer_id=customer_id).all():
            subscription.customer_name = customer.name
        self.db.commit()
        self.db.refresh(customer)
        return self._customer_schema(customer)

    def delete_customer(self, customer_id: int) -> bool:
        customer = self.db.get(CustomerModel, customer_id)
        if customer is None:
            return False
        self.db.delete(customer)
        for subscription in self.db.query(SubscriptionModel).filter_by(customer_id=customer_id).all():
            self.db.delete(subscription)
        self.db.commit()
        return True

    def list_subscriptions(
        self,
        *,
        search: str | None = None,
        status: str | None = None,
        customer_id: int | None = None,
        content_template_id: int | None = None,
        deliver_channel: str | None = None,
    ) -> list[Subscription]:
        query = self.db.query(SubscriptionModel)
        if search:
            pattern = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    SubscriptionModel.customer_name.ilike(pattern),
                    SubscriptionModel.content_template_name.ilike(pattern),
                    SubscriptionModel.deliver_address.ilike(pattern),
                    SubscriptionModel.frequency.ilike(pattern),
                    SubscriptionModel.notes.ilike(pattern),
                )
            )
        if customer_id:
            query = query.filter(SubscriptionModel.customer_id == customer_id)
        if content_template_id:
            query = query.filter(SubscriptionModel.content_template_id == content_template_id)
        if deliver_channel:
            query = query.filter(SubscriptionModel.deliver_channel == deliver_channel)
        subscriptions = query.order_by(SubscriptionModel.created_at.desc()).all()
        schemas = [self._subscription_schema(subscription) for subscription in subscriptions]
        if status:
            schemas = [subscription for subscription in schemas if subscription.status == status or subscription.expiry_status == status]
        return schemas

    def _subscription_names(self, payload: SubscriptionCreate | SubscriptionUpdate) -> tuple[str, str]:
        customer = self.db.get(CustomerModel, payload.customer_id)
        template = self.db.get(ContentTemplate, payload.content_template_id) if payload.content_template_id else None
        return customer.name if customer else "", template.name if template else ""

    def validate_subscription(self, payload: SubscriptionCreate | SubscriptionUpdate) -> str | None:
        if payload.content_template_id and self.db.get(ContentTemplate, payload.content_template_id) is None:
            return "Content label not found."
        if payload.duration_days is not None and payload.duration_days <= 0:
            return "Duration days must be greater than 0."
        if payload.start_date and payload.end_date and payload.end_date < payload.start_date:
            return "End date must be on or after start date."
        customer = self.db.get(CustomerModel, payload.customer_id)
        if customer is None:
            return "Customer not found."
        return None

    def create_subscription(self, payload: SubscriptionCreate) -> Subscription:
        validation_error = self.validate_subscription(payload)
        if validation_error:
            raise ValueError(validation_error)
        customer_name, template_name = self._subscription_names(payload)
        end_date = payload.end_date
        if end_date is None and payload.start_date is not None and payload.duration_days:
            end_date = payload.start_date + timedelta(days=payload.duration_days)
        subscription = SubscriptionModel(
            customer_id=payload.customer_id,
            customer_name=customer_name,
            content_template_id=payload.content_template_id,
            content_template_name=template_name,
            deliver_channel=payload.deliver_channel,
            deliver_address=payload.deliver_address,
            frequency=payload.frequency,
            start_date=payload.start_date,
            end_date=end_date,
            duration_days=payload.duration_days,
            status=payload.status,
            notes=payload.notes,
        )
        self.db.add(subscription)
        self.db.commit()
        self.db.refresh(subscription)
        return self._subscription_schema(subscription)

    def update_subscription(self, subscription_id: int, payload: SubscriptionUpdate) -> Subscription | None:
        subscription = self.db.get(SubscriptionModel, subscription_id)
        if subscription is None:
            return None
        validation_error = self.validate_subscription(payload)
        if validation_error:
            raise ValueError(validation_error)
        customer_name, template_name = self._subscription_names(payload)
        end_date = payload.end_date
        if end_date is None and payload.start_date is not None and payload.duration_days:
            end_date = payload.start_date + timedelta(days=payload.duration_days)
        subscription.customer_id = payload.customer_id
        subscription.customer_name = customer_name
        subscription.content_template_id = payload.content_template_id
        subscription.content_template_name = template_name
        subscription.deliver_channel = payload.deliver_channel
        subscription.deliver_address = payload.deliver_address
        subscription.frequency = payload.frequency
        subscription.start_date = payload.start_date
        subscription.end_date = end_date
        subscription.duration_days = payload.duration_days
        subscription.status = payload.status
        subscription.notes = payload.notes
        self.db.commit()
        self.db.refresh(subscription)
        return self._subscription_schema(subscription)

    def delete_subscription(self, subscription_id: int) -> bool:
        subscription = self.db.get(SubscriptionModel, subscription_id)
        if subscription is None:
            return False
        self.db.delete(subscription)
        self.db.commit()
        return True

    def dashboard_summary(self) -> DashboardSummary:
        customers = self.db.query(CustomerModel).count()
        subscriptions = [self._subscription_schema(item) for item in self.db.query(SubscriptionModel).all()]
        active = [item for item in subscriptions if item.status == "active" and item.expiry_status != "expired"]
        expiring = [item for item in subscriptions if item.expiry_status == "expiring_soon"]
        expired = [item for item in subscriptions if item.expiry_status == "expired"]
        recent_rows = (
            self.db.query(SubscriptionModel).order_by(SubscriptionModel.created_at.desc()).limit(5).all()
        )
        return DashboardSummary(
            customer_count=customers,
            active_subscription_count=len(active),
            expiring_soon_count=len(expiring),
            expired_subscription_count=len(expired),
            recent_subscriptions=[self._subscription_schema(item) for item in recent_rows],
        )
