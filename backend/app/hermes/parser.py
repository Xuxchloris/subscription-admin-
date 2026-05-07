import json
import re
from typing import Any

from app.schemas.jobs import HermesJob, JobStatus


def parse_job_ids(output: str) -> set[str]:
    ids: set[str] = set()
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.lower().startswith("id "):
            continue
        if re.match(r"^[A-Za-z][A-Za-z ]+:", stripped):
            continue
        match = re.match(r"^([A-Za-z0-9_-]{3,})\s+(?:\[[A-Za-z_-]+\]|\S+)", stripped)
        if match:
            ids.add(match.group(1))
    return ids


def parse_status_text(output: str) -> dict[str, Any]:
    lower = output.lower()
    return {
        "gateway_running": "running" in lower and "not running" not in lower,
        "raw": output,
    }


def parse_list_output(output: str) -> list[HermesJob]:
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError:
        return [HermesJob(id=job_id, raw=output) for job_id in sorted(parse_job_ids(output))]

    if isinstance(parsed, dict) and isinstance(parsed.get("jobs"), list):
        items = parsed["jobs"]
    elif isinstance(parsed, list):
        items = parsed
    else:
        items = []

    jobs: list[HermesJob] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        status_value = str(item.get("status", "unknown")).lower()
        if status_value == "paused":
            status = JobStatus.paused
        elif status_value in {"active", "enabled", "running"}:
            status = JobStatus.active
        else:
            status = JobStatus.unknown
        jobs.append(
            HermesJob(
                id=str(item.get("id", item.get("job_id", ""))),
                name=str(item.get("name", "")),
                prompt=str(item.get("prompt", "")),
                schedule=str(item.get("schedule", "")),
                deliver=str(item.get("deliver", "")),
                skills=list(item.get("skills", []))
                if isinstance(item.get("skills", []), list)
                else [],
                status=status if item.get("id") or item.get("job_id") else JobStatus.unknown,
                next_run_at=item.get("next_run_at"),
                raw=item,
            )
        )
    return [job for job in jobs if job.id]
