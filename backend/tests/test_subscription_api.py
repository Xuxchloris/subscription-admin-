from fastapi.testclient import TestClient

from app.api import customers as customers_api
from app.api import subscriptions as subscriptions_api
from app.main import app
from app.schemas.subscriptions import Customer, DashboardSummary, Subscription


def test_customer_subscription_and_summary_api(monkeypatch):
    class FakeService:
        def list_customers(self):
            return [Customer(id=1, name="客户A", contact="alice@example.com", status="active", notes="")]

        def create_customer(self, payload):
            return Customer(id=1, name=payload.name, contact=payload.contact, status=payload.status, notes=payload.notes)

        def list_subscriptions(self):
            return [
                Subscription(
                    id=1,
                    customer_id=1,
                    customer_name="客户A",
                    content_template_name="AI 资讯",
                    deliver_channel="feishu",
                    deliver_address="飞书群",
                    frequency="每天 08:00",
                    status="active",
                    expiry_status="active",
                )
            ]

        def validate_subscription(self, payload):
            return None

        def create_subscription(self, payload):
            return Subscription(
                id=1,
                customer_id=payload.customer_id,
                customer_name="客户A",
                content_template_name="AI 资讯",
                deliver_channel=payload.deliver_channel,
                deliver_address=payload.deliver_address,
                frequency=payload.frequency,
                status=payload.status,
            )

        def dashboard_summary(self):
            return DashboardSummary(customer_count=1, active_subscription_count=1)

    class RejectingService(FakeService):
        def validate_subscription(self, payload):
            return "Customer not found."

    monkeypatch.setattr(customers_api, "_service", lambda db: FakeService())
    monkeypatch.setattr(subscriptions_api, "_service", lambda db: FakeService())
    app.dependency_overrides[customers_api.require_admin] = lambda: "admin"
    app.dependency_overrides[subscriptions_api.require_admin] = lambda: "admin"
    client = TestClient(app)

    try:
        customer_response = client.post(
            "/api/customers",
            json={"name": "客户A", "contact": "alice@example.com", "status": "active", "notes": ""},
        )
        subscription_response = client.post(
            "/api/subscriptions",
            json={
                "customer_id": 1,
                "content_template_id": None,
                "deliver_channel": "feishu",
                "deliver_address": "飞书群",
                "frequency": "每天 08:00",
                "status": "active",
            },
        )
        summary_response = client.get("/api/subscriptions/summary")
    finally:
        app.dependency_overrides.clear()

    assert customer_response.status_code == 200
    assert customer_response.json()["data"]["name"] == "客户A"
    assert subscription_response.json()["data"]["deliver_channel"] == "feishu"
    assert summary_response.json()["data"]["active_subscription_count"] == 1

    monkeypatch.setattr(subscriptions_api, "_service", lambda db: RejectingService())
    app.dependency_overrides[subscriptions_api.require_admin] = lambda: "admin"
    client = TestClient(app)

    try:
        invalid_response = client.post(
            "/api/subscriptions",
            json={"customer_id": 999, "deliver_channel": "feishu", "duration_days": 7},
        )
    finally:
        app.dependency_overrides.clear()

    assert invalid_response.status_code == 400
    assert invalid_response.json()["error"]["code"] == "SUBSCRIPTION_INVALID"
