from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.health import build_hermes_health
from app.db.base import Base
from app.hermes.adapter import HermesCommandResult
from app.main import app
from app.models.operation_result import OperationResult
from app.schemas.jobs import HermesJob, JobStatus


def test_root_health_returns_ok():
    client = TestClient(app)
    response = client.get("/api/health/ping")

    assert response.status_code == 200
    assert response.json() == {"success": True, "data": {"status": "ok"}, "error": None}


def test_hermes_health_includes_cli_storage_last_operation_and_job_counts(monkeypatch, tmp_path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    (tmp_path / "cron" / "output").mkdir(parents=True)

    class FakeAdapter:
        def status(self):
            return (
                HermesCommandResult(["hermes", "cron", "status"], 0, "running", ""),
                {"gateway_running": True, "raw": "running"},
            )

        def list_jobs(self):
            return (
                HermesCommandResult(["hermes", "cron", "list"], 0, "", ""),
                [
                    HermesJob(id="active", status=JobStatus.active),
                    HermesJob(id="paused", status=JobStatus.paused),
                    HermesJob(id="unknown", status=JobStatus.unknown),
                ],
            )

    class FakeSettings:
        hermes_home = tmp_path

    monkeypatch.setattr("app.api.health.HermesCliAdapter", FakeAdapter)
    monkeypatch.setattr("app.api.health.get_settings", lambda: FakeSettings())

    with Session(engine) as session:
        session.add(
            OperationResult(
                operation="pause_job",
                hermes_job_id="paused",
                status="failed",
                stdout="",
                stderr="could not confirm",
            )
        )
        session.commit()

        response = build_hermes_health(session)

    assert response["cli"]["available"] is True
    assert response["gateway"]["running"] is True
    assert response["cron_data"]["readable"] is True
    assert response["output_dir"]["readable"] is True
    assert response["last_admin_operation"]["status"] == "failed"
    assert response["job_counts"] == {
        "total": 3,
        "active": 1,
        "paused": 1,
        "sync_problems": 1,
    }
