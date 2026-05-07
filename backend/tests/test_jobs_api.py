from fastapi.testclient import TestClient

from app.api import jobs as jobs_api
from app.api import templates as templates_api
from app.main import app
from app.schemas.jobs import ContentDelivery, ContentGroup


def test_jobs_requires_auth():
    client = TestClient(app)
    response = client.get("/api/jobs")

    assert response.status_code == 401
    assert response.json()["success"] is False


def test_content_groups_api_returns_grouped_jobs(monkeypatch):
    class FakeService:
        def list_content_groups(self):
            return [
                ContentGroup(
                    content_id="content-1",
                    title="Daily content",
                    owner_label="Client A",
                    prompt="Write today's brief",
                    skills=["writer"],
                    deliveries=[
                        ContentDelivery(
                            job_id="job-1",
                            label="Feishu morning",
                            schedule="30 6 * * *",
                            deliver="feishu",
                        )
                    ],
                )
            ]

    monkeypatch.setattr(jobs_api, "_service", lambda db: FakeService())
    app.dependency_overrides[jobs_api.require_admin] = lambda: "admin"
    client = TestClient(app)

    try:
        response = client.get("/api/jobs/content-groups")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["data"][0]["content_id"] == "content-1"
    assert response.json()["data"][0]["deliveries"][0]["deliver"] == "feishu"


def test_create_content_group_api_accepts_multiple_deliveries(monkeypatch):
    captured = {}

    class FakeService:
        def create_content_group(self, payload):
            captured["payload"] = payload
            return ContentGroup(
                content_id="content-1",
                title=payload.title,
                owner_label=payload.owner_label,
                prompt=payload.prompt,
                skills=payload.skills,
                deliveries=[
                    ContentDelivery(job_id="job-1", schedule=payload.deliveries[0].schedule, deliver=payload.deliveries[0].deliver),
                    ContentDelivery(job_id="job-2", schedule=payload.deliveries[1].schedule, deliver=payload.deliveries[1].deliver),
                ],
            )

    monkeypatch.setattr(jobs_api, "_service", lambda db: FakeService())
    app.dependency_overrides[jobs_api.require_admin] = lambda: "admin"
    client = TestClient(app)

    try:
        response = client.post(
            "/api/jobs/content-groups",
            json={
                "owner_label": "Client A",
                "title": "Daily content",
                "prompt": "Write today's brief",
                "skills": ["writer"],
                "deliveries": [
                    {"schedule": "30 6 * * *", "deliver": "feishu", "label": "Feishu morning"},
                    {"schedule": "0 9 * * *", "deliver": "local", "label": "Local archive"},
                ],
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["data"]["title"] == "Daily content"
    assert [item["deliver"] for item in response.json()["data"]["deliveries"]] == ["feishu", "local"]
    assert captured["payload"].deliveries[0].label == "Feishu morning"


def test_templates_api_crud(monkeypatch):
    class Template:
        def __init__(self, id=1, name="AI 资讯"):
            self.id = id
            self.name = name
            self.prompt = "抓取 AI 资讯"
            self.skills = ["trend-scout"]
            self.notes = ""
            self.created_at = None
            self.updated_at = None

        def model_dump(self):
            return self.__dict__

    class FakeService:
        def list_templates(self):
            return [Template()]

        def create_template(self, payload):
            return Template(name=payload.name)

        def update_template(self, template_id, payload):
            return Template(id=template_id, name=payload.name)

        def delete_template(self, template_id):
            return True

    monkeypatch.setattr(templates_api, "_service", lambda db: FakeService())
    app.dependency_overrides[templates_api.require_admin] = lambda: "admin"
    client = TestClient(app)

    try:
        list_response = client.get("/api/templates")
        create_response = client.post(
            "/api/templates",
            json={"name": "AI 资讯", "prompt": "抓取 AI 资讯", "skills": ["trend-scout"], "notes": ""},
        )
        update_response = client.put(
            "/api/templates/1",
            json={"name": "AI 工具", "prompt": "抓取 AI 工具", "skills": ["writer"], "notes": ""},
        )
        delete_response = client.delete("/api/templates/1")
    finally:
        app.dependency_overrides.clear()

    assert list_response.status_code == 200
    assert list_response.json()["data"][0]["name"] == "AI 资讯"
    assert create_response.json()["data"]["skills"] == ["trend-scout"]
    assert update_response.json()["data"]["name"] == "AI 工具"
    assert delete_response.json()["data"]["id"] == 1
