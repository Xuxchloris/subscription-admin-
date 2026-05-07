import subprocess
from dataclasses import dataclass

from app.core.config import Settings, get_settings
from app.hermes.parser import parse_list_output, parse_status_text
from app.schemas.jobs import HermesJob, JobCreate, JobUpdate


@dataclass(frozen=True)
class HermesCommandResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str
    error_category: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def combined_output(self) -> str:
        return "\n".join(part for part in [self.stdout.strip(), self.stderr.strip()] if part)


class HermesCliAdapter:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _run(self, args: list[str], timeout_seconds: int = 60) -> HermesCommandResult:
        full_args = [self.settings.hermes_binary, *args]
        try:
            completed = subprocess.run(
                full_args,
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
                check=False,
            )
        except FileNotFoundError as exc:
            return HermesCommandResult(
                args=full_args,
                returncode=127,
                stdout="",
                stderr=str(exc),
                error_category="cli_missing",
            )
        except (subprocess.TimeoutExpired, TimeoutError) as exc:
            stdout = exc.stdout if isinstance(exc, subprocess.TimeoutExpired) else ""
            stderr = exc.stderr if isinstance(exc, subprocess.TimeoutExpired) else str(exc)
            return HermesCommandResult(
                args=full_args,
                returncode=124,
                stdout=stdout or "",
                stderr=stderr or f"Hermes command timed out after {timeout_seconds} seconds.",
                error_category="timeout",
            )
        return HermesCommandResult(
            args=full_args,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def list_jobs(self) -> tuple[HermesCommandResult, list[HermesJob]]:
        result = self._run(["cron", "list"])
        return result, parse_list_output(result.stdout)

    def status(self) -> tuple[HermesCommandResult, dict]:
        result = self._run(["cron", "status"])
        return result, parse_status_text(result.stdout + "\n" + result.stderr)

    def create_job(self, payload: JobCreate) -> HermesCommandResult:
        args = ["cron", "create", payload.schedule, payload.prompt, "--name", payload.task_name]
        if payload.deliver:
            args.extend(["--deliver", payload.deliver])
        for skill in payload.skills:
            args.extend(["--skill", skill])
        return self._run(args)

    def edit_job(self, job_id: str, payload: JobUpdate) -> HermesCommandResult:
        args = [
            "cron",
            "edit",
            job_id,
            "--schedule",
            payload.schedule,
            "--prompt",
            payload.prompt,
            "--name",
            payload.task_name,
            "--deliver",
            payload.deliver,
            "--clear-skills",
        ]
        for skill in payload.skills:
            args.extend(["--add-skill", skill])
        return self._run(args)

    def pause_job(self, job_id: str) -> HermesCommandResult:
        return self._run(["cron", "pause", job_id])

    def resume_job(self, job_id: str) -> HermesCommandResult:
        return self._run(["cron", "resume", job_id])

    def run_job(self, job_id: str) -> HermesCommandResult:
        return self._run(["cron", "run", job_id])

    def remove_job(self, job_id: str) -> HermesCommandResult:
        return self._run(["cron", "remove", job_id])
