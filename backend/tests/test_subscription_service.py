from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.content_template import ContentTemplate
from app.schemas.subscriptions import CustomerCreate, SubscriptionCreate
from app.services.subscription_service import SubscriptionService


def test_subscription_service_creates_customer_subscription_and_summary():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(ContentTemplate(name="AI 资讯", prompt="抓取 AI 资讯", skills_json='["trend-scout"]'))
        session.commit()

        service = SubscriptionService(session)
        customer = service.create_customer(
            CustomerCreate(name="客户A", contact="alice@example.com", status="active", notes="VIP")
        )
        subscription = service.create_subscription(
            SubscriptionCreate(
                customer_id=customer.id,
                content_template_id=1,
                deliver_channel="feishu",
                deliver_address="飞书群",
                frequency="每天 08:00",
                start_date=date.today(),
                duration_days=7,
                status="active",
                notes="首月试用",
            )
        )
        summary = service.dashboard_summary()

    assert customer.name == "客户A"
    assert subscription.customer_name == "客户A"
    assert subscription.content_template_name == "AI 资讯"
    assert subscription.end_date == date.today() + timedelta(days=7)
    assert subscription.expiry_status == "expiring_soon"
    assert summary.customer_count == 1
    assert summary.active_subscription_count == 1
    assert summary.expiring_soon_count == 1


def test_subscription_service_marks_past_end_date_as_expired():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        service = SubscriptionService(session)
        customer = service.create_customer(CustomerCreate(name="客户B"))
        subscription = service.create_subscription(
            SubscriptionCreate(
                customer_id=customer.id,
                deliver_channel="wechat",
                deliver_address="微信",
                frequency="每周一",
                start_date=date.today() - timedelta(days=10),
                end_date=date.today() - timedelta(days=1),
                status="active",
            )
        )

    assert subscription.status == "expired"
    assert subscription.expiry_status == "expired"
    assert subscription.days_remaining == 0


def test_subscription_service_filters_by_search_status_customer_and_template():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add_all(
            [
                ContentTemplate(name="AI 资讯", prompt="抓取 AI 资讯", skills_json='["trend-scout"]'),
                ContentTemplate(name="小红书选题", prompt="抓取小红书选题", skills_json='["xhs"]'),
            ]
        )
        session.commit()

        service = SubscriptionService(session)
        customer_a = service.create_customer(CustomerCreate(name="客户A", contact="alice@example.com"))
        customer_b = service.create_customer(CustomerCreate(name="客户B", contact="bob@example.com"))
        service.create_subscription(
            SubscriptionCreate(
                customer_id=customer_a.id,
                content_template_id=1,
                deliver_channel="feishu",
                deliver_address="飞书群",
                frequency="每天 08:00",
                start_date=date.today(),
                duration_days=30,
                status="active",
            )
        )
        service.create_subscription(
            SubscriptionCreate(
                customer_id=customer_b.id,
                content_template_id=2,
                deliver_channel="wechat",
                deliver_address="微信",
                frequency="每周一 09:00",
                start_date=date.today() - timedelta(days=10),
                end_date=date.today() - timedelta(days=1),
                status="active",
            )
        )

        by_search = service.list_subscriptions(search="飞书")
        by_status = service.list_subscriptions(status="expired")
        by_customer = service.list_subscriptions(customer_id=customer_a.id)
        by_template = service.list_subscriptions(content_template_id=2)

    assert [item.customer_name for item in by_search] == ["客户A"]
    assert [item.customer_name for item in by_status] == ["客户B"]
    assert [item.customer_name for item in by_customer] == ["客户A"]
    assert [item.content_template_name for item in by_template] == ["小红书选题"]


def test_subscription_service_rejects_missing_customer_and_invalid_duration():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        service = SubscriptionService(session)

        missing_customer = service.validate_subscription(
            SubscriptionCreate(customer_id=999, deliver_channel="qq", duration_days=7)
        )
        invalid_duration = service.validate_subscription(
            SubscriptionCreate(customer_id=1, deliver_channel="qq", duration_days=0)
        )

    assert missing_customer == "Customer not found."
    assert invalid_duration == "Duration days must be greater than 0."
