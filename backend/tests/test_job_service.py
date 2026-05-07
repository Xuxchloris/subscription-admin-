from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.job_metadata import JobMetadata, SyncStatus


def test_job_metadata_persists_owner_label_and_sync_status():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        job = JobMetadata(
            hermes_job_id="job-123",
            owner_label="alice@example.com",
            task_name="Morning brief",
            notes="Paid subscriber",
            sync_status=SyncStatus.synced,
        )
        session.add(job)
        session.commit()

        saved = session.query(JobMetadata).filter_by(hermes_job_id="job-123").one()

    assert saved.owner_label == "alice@example.com"
    assert saved.sync_status == SyncStatus.synced


from dataclasses import dataclass
import os
from pathlib import Path

from app.hermes.adapter import HermesCommandResult
from app.models.audit import AuditEvent
from app.models.operation_result import OperationResult
from app.schemas.jobs import HermesJob, JobCreate, JobStatus, JobUpdate
from app.services.job_service import JobService, _active_operations


def setup_function():
    _active_operations.clear()


def teardown_function():
    _active_operations.clear()


@dataclass
class FakeHermes:
    created: bool = False

    def create_job(self, payload):
        self.created = True
        return HermesCommandResult(["hermes", "cron", "create"], 0, "created abc123", "")

    def list_jobs(self):
        if self.created:
            return (
                HermesCommandResult(["hermes", "cron", "list"], 0, "abc123 Morning brief", ""),
                [HermesJob(id="abc123", name="Morning brief", status=JobStatus.active)],
            )
        return HermesCommandResult(["hermes", "cron", "list"], 0, "", ""), []


def test_create_job_writes_metadata_only_after_hermes_confirmation():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        service = JobService(session, hermes=FakeHermes())
        created = service.create_job(
            JobCreate(
                owner_label="alice@example.com",
                task_name="Morning brief",
                prompt="Send morning brief",
                schedule="every 1h",
            )
        )

        metadata = session.query(JobMetadata).filter_by(hermes_job_id="abc123").one()
        audit = session.query(AuditEvent).filter_by(operation="create_job").one()

    assert created.id == "abc123"
    assert metadata.owner_label == "alice@example.com"
    assert metadata.sync_status == SyncStatus.synced
    assert audit.status == "success"


class StaticHermes:
    def __init__(self, jobs):
        self.jobs = jobs

    def list_jobs(self):
        return HermesCommandResult(["hermes", "cron", "list"], 0, "", ""), self.jobs


class MultiDeliveryHermes:
    def __init__(self):
        self.created_payloads = []
        self.jobs = []
        self.paused_ids = []

    def list_jobs(self):
        return HermesCommandResult(["hermes", "cron", "list"], 0, "", ""), self.jobs

    def create_job(self, payload):
        self.created_payloads.append(payload)
        job_id = f"job-{len(self.created_payloads)}"
        job = HermesJob(
            id=job_id,
            name=payload.task_name,
            prompt=payload.prompt,
            schedule=payload.schedule,
            deliver=payload.deliver,
            skills=payload.skills,
            status=JobStatus.active,
        )
        self.jobs.append(job)
        return HermesCommandResult(["hermes", "cron", "create"], 0, f"created {job_id}", "")

    def pause_job(self, job_id):
        self.paused_ids.append(job_id)
        self.jobs = [
            job.model_copy(update={"status": JobStatus.paused}) if job.id == job_id else job
            for job in self.jobs
        ]
        return HermesCommandResult(["hermes", "cron", "pause", job_id], 0, "paused", "")


def test_list_jobs_merges_hermes_jobs_with_admin_metadata_and_marks_orphans():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(
            JobMetadata(
                hermes_job_id="abc123",
                owner_label="alice@example.com",
                task_name="Morning brief",
                notes="Paid subscriber",
                sync_status=SyncStatus.synced,
                last_error="",
            )
        )
        session.add(
            JobMetadata(
                hermes_job_id="missing",
                owner_label="bob@example.com",
                task_name="Missing task",
                notes="Needs repair",
                sync_status=SyncStatus.synced,
                last_error="",
            )
        )
        session.commit()

        service = JobService(
            session,
            hermes=StaticHermes(
                [HermesJob(id="abc123", name="Hermes name", status=JobStatus.active)]
            ),
        )
        jobs = service.list_jobs()
        missing = session.query(JobMetadata).filter_by(hermes_job_id="missing").one()

    assert len(jobs) == 1
    assert jobs[0].id == "abc123"
    assert jobs[0].owner_label == "alice@example.com"
    assert jobs[0].task_name == "Morning brief"
    assert jobs[0].notes == "Paid subscriber"
    assert jobs[0].sync_status == SyncStatus.synced
    assert jobs[0].last_error == ""
    assert jobs[0].last_run_result is None
    assert missing.sync_status == SyncStatus.sync_error
    assert missing.last_error == "Hermes job missing from source of truth."


def test_list_content_groups_merges_jobs_by_content_id_and_delivery():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(
            JobMetadata(
                hermes_job_id="job-1",
                content_id="content-1",
                content_title="Daily content",
                owner_label="Client A",
                task_name="Daily content",
                notes="Primary package",
                sync_status=SyncStatus.synced,
            )
        )
        session.add(
            JobMetadata(
                hermes_job_id="job-2",
                content_id="content-1",
                content_title="Daily content",
                owner_label="Client A",
                task_name="Daily content",
                notes="Primary package",
                sync_status=SyncStatus.synced,
            )
        )
        session.commit()

        service = JobService(
            session,
            hermes=StaticHermes(
                [
                    HermesJob(
                        id="job-1",
                        name="Daily content",
                        prompt="Write today's brief",
                        schedule="30 6 * * *",
                        deliver="feishu",
                        skills=["writer"],
                        status=JobStatus.active,
                    ),
                    HermesJob(
                        id="job-2",
                        name="Daily content",
                        prompt="Write today's brief",
                        schedule="0 9 * * *",
                        deliver="local",
                        skills=["writer"],
                        status=JobStatus.paused,
                    ),
                ]
            ),
        )

        groups = service.list_content_groups()

    assert len(groups) == 1
    assert groups[0].content_id == "content-1"
    assert groups[0].title == "Daily content"
    assert groups[0].owner_label == "Client A"
    assert groups[0].prompt == "Write today's brief"
    assert groups[0].skills == ["writer"]
    assert [delivery.deliver for delivery in groups[0].deliveries] == ["feishu", "local"]
    assert [delivery.job_id for delivery in groups[0].deliveries] == ["job-1", "job-2"]


def test_create_content_group_creates_one_hermes_job_per_delivery():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    hermes = MultiDeliveryHermes()

    with Session(engine) as session:
        service = JobService(session, hermes=hermes)
        group = service.create_content_group(
            {
                "owner_label": "Client A",
                "title": "Daily content",
                "prompt": "Write today's brief",
                "skills": ["writer", "trend-scout"],
                "notes": "Primary package",
                "deliveries": [
                    {"schedule": "30 6 * * *", "deliver": "feishu", "label": "Feishu morning"},
                    {"schedule": "0 9 * * *", "deliver": "local", "label": "Local archive"},
                ],
            }
        )

        metadata = session.query(JobMetadata).order_by(JobMetadata.hermes_job_id).all()

    assert len(group.deliveries) == 2
    assert [payload.deliver for payload in hermes.created_payloads] == ["feishu", "local"]
    assert [payload.schedule for payload in hermes.created_payloads] == ["30 6 * * *", "0 9 * * *"]
    assert len({item.content_id for item in metadata}) == 1
    assert metadata[0].content_title == "Daily content"
    assert metadata[1].content_title == "Daily content"


def test_create_content_group_persists_template_and_expiry_metadata():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    hermes = MultiDeliveryHermes()

    with Session(engine) as session:
        service = JobService(session, hermes=hermes)
        group = service.create_content_group(
            {
                "owner_label": "客户项目A",
                "title": "AI 工具资讯",
                "prompt": "抓取 AI 工具资讯",
                "skills": ["trend-scout"],
                "content_template_id": 7,
                "content_template_name": "AI 工具资讯",
                "duration_days": 14,
                "deliveries": [
                    {"schedule": "30 6 * * *", "deliver": "feishu", "label": "飞书"},
                ],
            }
        )

        metadata = session.query(JobMetadata).filter_by(hermes_job_id="job-1").one()

    assert group.content_template_id == 7
    assert group.content_template_name == "AI 工具资讯"
    assert group.duration_days == 14
    assert group.expires_at is not None
    assert group.expiry_status == "active"
    assert metadata.owner_label == "客户项目A"
    assert metadata.content_template_id == 7
    assert metadata.content_template_name == "AI 工具资讯"
    assert metadata.duration_days == 14
    assert metadata.expires_at is not None


def test_list_content_groups_pauses_expired_active_jobs_and_shows_countdown():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    hermes = MultiDeliveryHermes()
    hermes.jobs = [
        HermesJob(
            id="job-1",
            name="Expired content",
            prompt="Expired prompt",
            schedule="30 6 * * *",
            deliver="feishu",
            skills=["trend-scout"],
            status=JobStatus.active,
        )
    ]

    with Session(engine) as session:
        session.add(
            JobMetadata(
                hermes_job_id="job-1",
                content_id="content-1",
                content_title="Expired content",
                owner_label="客户项目A",
                task_name="Expired content",
                sync_status=SyncStatus.synced,
                duration_days=1,
                expires_at=service_time_past(),
            )
        )
        session.commit()

        service = JobService(session, hermes=hermes)
        groups = service.list_content_groups()
        metadata = session.query(JobMetadata).filter_by(hermes_job_id="job-1").one()

    assert hermes.paused_ids == ["job-1"]
    assert metadata.sync_status == SyncStatus.expired
    assert metadata.expired_at is not None
    assert groups[0].expiry_status == "expired"
    assert groups[0].seconds_remaining == 0
    assert groups[0].deliveries[0].expiry_status == "expired"


def service_time_past():
    from datetime import datetime, timedelta, timezone

    return datetime.now(timezone.utc) - timedelta(minutes=1)


class UnknownPauseHermes:
    def pause_job(self, job_id):
        return HermesCommandResult(["hermes", "cron", "pause", job_id], 0, "paused", "")

    def list_jobs(self):
        return (
            HermesCommandResult(["hermes", "cron", "list"], 0, "abc123 Morning brief", ""),
            [HermesJob(id="abc123", name="Morning brief", status=JobStatus.unknown)],
        )


class BlockingHermes:
    def pause_job(self, job_id):
        return HermesCommandResult(["hermes", "cron", "pause", job_id], 0, "paused", "")

    def list_jobs(self):
        return (
            HermesCommandResult(["hermes", "cron", "list"], 0, "abc123 Morning brief", ""),
            [HermesJob(id="abc123", name="Morning brief", status=JobStatus.paused)],
        )


def test_pause_unknown_confirmation_fails_and_records_audit_and_result():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        service = JobService(session, hermes=UnknownPauseHermes())

        try:
            service.pause_job("abc123")
        except Exception as exc:
            assert exc.error.code == "HERMES_OPERATION_FAILED"
        else:
            raise AssertionError("Expected pause confirmation failure.")

        audit = session.query(AuditEvent).filter_by(operation="pause_job").one()
        result = session.query(OperationResult).filter_by(operation="pause_job").one()

    assert audit.status == "failed"
    assert audit.error_message == "Paused task could not be confirmed."
    assert result.status == "failed"
    assert result.stdout == "paused"


def test_operation_lock_blocks_duplicate_job_operations():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        service = JobService(session, hermes=BlockingHermes())
        service._active_operations.add("abc123")

        try:
            service.pause_job("abc123")
        except Exception as exc:
            assert exc.error.code == "HERMES_OPERATION_IN_PROGRESS"
        else:
            raise AssertionError("Expected duplicate operation to be blocked.")


class UpdateRawHermes:
    def edit_job(self, job_id, payload):
        return HermesCommandResult(["hermes", "cron", "edit", job_id], 0, "updated", "")

    def list_jobs(self):
        return (
            HermesCommandResult(["hermes", "cron", "list"], 0, "{}", ""),
            [
                HermesJob(
                    id="abc123",
                    name="Morning brief",
                    status=JobStatus.active,
                    raw={"id": "abc123", "name": "Wrong name"},
                )
            ],
        )


def test_update_fails_when_parse_output_contradicts_expected_changed_fields():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(
            JobMetadata(
                hermes_job_id="abc123",
                owner_label="alice@example.com",
                task_name="Morning brief",
                sync_status=SyncStatus.synced,
            )
        )
        session.commit()
        service = JobService(session, hermes=UpdateRawHermes())

        try:
            service.update_job(
                "abc123",
                JobUpdate(
                    owner_label="alice@example.com",
                    task_name="Evening brief",
                    prompt="Send evening brief",
                    schedule="every 2h",
                ),
            )
        except Exception as exc:
            assert exc.error.message == "Updated task could not be confirmed."
        else:
            raise AssertionError("Expected update confirmation failure.")

        metadata = session.query(JobMetadata).filter_by(hermes_job_id="abc123").one()
        audit = session.query(AuditEvent).filter_by(operation="update_job").one()

    assert metadata.sync_status == SyncStatus.last_operation_failed
    assert audit.status == "failed"


class JobRunsHermes(StaticHermes):
    pass


def test_list_job_runs_reads_recent_text_outputs_under_hermes_home(tmp_path):
    output_dir = tmp_path / "cron" / "output"
    output_dir.mkdir(parents=True)
    older = output_dir / "abc123-older.txt"
    newer = output_dir / "abc123-newer.log"
    other = output_dir / "other.txt"
    older.write_text("older run\n", encoding="utf-8")
    newer.write_text("newer run\n", encoding="utf-8")
    other.write_text("not this job\n", encoding="utf-8")
    os.utime(older, (1_700_000_000, 1_700_000_000))
    os.utime(newer, (1_700_000_100, 1_700_000_100))
    os.utime(other, (1_700_000_200, 1_700_000_200))

    service = JobService(
        db=None,
        hermes=JobRunsHermes([HermesJob(id="abc123", name="Morning brief")]),
        hermes_home=Path(tmp_path),
    )

    runs = service.list_job_runs("abc123")

    assert [run["file_name"] for run in runs] == ["abc123-newer.log", "abc123-older.txt"]
    assert runs[0]["content"] == "newer run\n"
