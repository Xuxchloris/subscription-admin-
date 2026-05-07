from app.hermes.parser import parse_job_ids, parse_list_output, parse_status_text
from app.core.config import Settings
from app.hermes.adapter import HermesCliAdapter
from app.schemas.jobs import JobCreate


def test_parse_job_ids_from_text_output():
    output = """
    ID        Name             Status
    abc123    Morning brief    active
    def456    Client update    paused
    """

    assert parse_job_ids(output) == {"abc123", "def456"}


def test_parse_job_ids_from_hermes_box_output_ignores_detail_labels():
    output = """
    ┌─────────────────────────────────────────────────────────────────────────┐
    │                         Scheduled Jobs                                  │
    └─────────────────────────────────────────────────────────────────────────┘

      06552a8fb5b7 [active]
        Name:      Deployment verification
        Schedule:  once in 30m
        Repeat:    0/1
        Next run:  2026-05-07T15:19:03.687397+08:00
        Deliver:   local

      f8c582422ea3 [paused]
        Name:      内容作战总览
        Schedule:  30 6 * * 1,4
        Repeat:    ∞
        Next run:  2026-05-11T06:30:00+08:00
        Deliver:   feishu
        Skills:    chinese-content-trend-scout
    """

    assert parse_job_ids(output) == {"06552a8fb5b7", "f8c582422ea3"}


def test_parse_status_text_reports_gateway_running():
    output = "Hermes cron scheduler: running\nJobs loaded: 2\n"

    status = parse_status_text(output)

    assert status["gateway_running"] is True
    assert status["raw"] == output


def test_parse_list_output_preserves_unknown_status():
    jobs = parse_list_output('[{"id": "abc123", "status": "mystery"}]')

    assert jobs[0].status.value == "unknown"


def test_create_job_builds_argument_array(monkeypatch):
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs

        class Completed:
            returncode = 0
            stdout = "created"
            stderr = ""

        return Completed()

    monkeypatch.setattr("app.hermes.adapter.subprocess.run", fake_run)
    adapter = HermesCliAdapter(Settings(hermes_binary="hermes"))

    result = adapter.create_job(
        JobCreate(
            owner_label="alice@example.com",
            task_name="Morning brief",
            prompt="Check server status",
            schedule="every 2h",
            deliver="local",
            skills=["blogwatcher"],
        )
    )

    assert result.ok is True
    assert captured["args"] == [
        "hermes",
        "cron",
        "create",
        "every 2h",
        "Check server status",
        "--name",
        "Morning brief",
        "--deliver",
        "local",
        "--skill",
        "blogwatcher",
    ]
    assert captured["kwargs"]["check"] is False
    assert "shell" not in captured["kwargs"]


def test_missing_hermes_binary_result_has_cli_missing_category(monkeypatch):
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("[Errno 2] No such file or directory: 'hermes'")

    monkeypatch.setattr("app.hermes.adapter.subprocess.run", fake_run)
    adapter = HermesCliAdapter(Settings(hermes_binary="hermes"))

    result = adapter.list_jobs()[0]

    assert result.returncode == 127
    assert result.error_category == "cli_missing"


def test_timeout_result_has_timeout_category(monkeypatch):
    def fake_run(*args, **kwargs):
        raise TimeoutError("timeout")

    monkeypatch.setattr("app.hermes.adapter.subprocess.run", fake_run)
    adapter = HermesCliAdapter(Settings(hermes_binary="hermes"))

    result = adapter._run(["cron", "list"], timeout_seconds=1)

    assert result.returncode == 124
    assert result.error_category == "timeout"
