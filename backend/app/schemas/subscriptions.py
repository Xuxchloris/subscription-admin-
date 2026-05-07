from datetime import date

from pydantic import BaseModel, Field


class CustomerBase(BaseModel):
    name: str
    contact: str = ""
    status: str = "active"
    notes: str = ""


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(CustomerBase):
    pass


class Customer(CustomerBase):
    id: int
    created_at: str | None = None
    updated_at: str | None = None


class SubscriptionBase(BaseModel):
    customer_id: int
    content_template_id: int | None = None
    deliver_channel: str = "local"
    deliver_address: str = ""
    frequency: str = ""
    start_date: date | None = None
    end_date: date | None = None
    duration_days: int | None = None
    status: str = "active"
    notes: str = ""


class SubscriptionCreate(SubscriptionBase):
    pass


class SubscriptionUpdate(SubscriptionBase):
    pass


class Subscription(SubscriptionBase):
    id: int
    customer_name: str = ""
    content_template_name: str = ""
    expiry_status: str = "active"
    days_remaining: int | None = None
    created_at: str | None = None
    updated_at: str | None = None


class DashboardSummary(BaseModel):
    customer_count: int = 0
    active_subscription_count: int = 0
    expiring_soon_count: int = 0
    expired_subscription_count: int = 0
    recent_subscriptions: list[Subscription] = Field(default_factory=list)
