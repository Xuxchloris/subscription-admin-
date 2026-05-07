from enum import Enum

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    active = "active"
    paused = "paused"
    unknown = "unknown"


class HermesJob(BaseModel):
    id: str
    name: str = ""
    prompt: str = ""
    schedule: str = ""
    deliver: str = ""
    skills: list[str] = Field(default_factory=list)
    status: JobStatus = JobStatus.unknown
    next_run_at: str | None = None
    raw: dict | str | None = None
    owner_label: str = ""
    task_name: str = ""
    notes: str = ""
    sync_status: str = "synced"
    last_error: str = ""
    last_run_result: dict | None = None
    content_id: str = ""
    content_title: str = ""
    content_template_id: int | None = None
    content_template_name: str = ""
    delivery_label: str = ""
    duration_days: int | None = None
    starts_at: str | None = None
    expires_at: str | None = None
    expired_at: str | None = None
    expiry_status: str = "permanent"
    seconds_remaining: int | None = None


class JobCreate(BaseModel):
    owner_label: str
    task_name: str
    prompt: str
    schedule: str
    deliver: str = "local"
    skills: list[str] = Field(default_factory=list)
    notes: str = ""


class JobUpdate(BaseModel):
    owner_label: str
    task_name: str
    prompt: str
    schedule: str
    deliver: str = "local"
    skills: list[str] = Field(default_factory=list)
    notes: str = ""


class ContentDeliveryCreate(BaseModel):
    schedule: str
    deliver: str = "local"
    label: str = ""


class ContentGroupCreate(BaseModel):
    owner_label: str
    title: str
    prompt: str
    skills: list[str] = Field(default_factory=list)
    notes: str = ""
    content_template_id: int | None = None
    content_template_name: str = ""
    duration_days: int | None = None
    deliveries: list[ContentDeliveryCreate] = Field(default_factory=list)


class ContentDelivery(BaseModel):
    job_id: str
    label: str = ""
    schedule: str = ""
    deliver: str = ""
    status: JobStatus = JobStatus.unknown
    next_run_at: str | None = None
    sync_status: str = "synced"
    last_error: str = ""
    last_run_result: dict | None = None
    expires_at: str | None = None
    expired_at: str | None = None
    expiry_status: str = "permanent"
    seconds_remaining: int | None = None


class ContentGroup(BaseModel):
    content_id: str
    title: str
    owner_label: str = ""
    prompt: str = ""
    skills: list[str] = Field(default_factory=list)
    notes: str = ""
    content_template_id: int | None = None
    content_template_name: str = ""
    duration_days: int | None = None
    expires_at: str | None = None
    expiry_status: str = "permanent"
    seconds_remaining: int | None = None
    deliveries: list[ContentDelivery] = Field(default_factory=list)


class ContentTemplateBase(BaseModel):
    name: str
    prompt: str
    skills: list[str] = Field(default_factory=list)
    notes: str = ""


class ContentTemplateCreate(ContentTemplateBase):
    pass


class ContentTemplateUpdate(ContentTemplateBase):
    pass


class ContentTemplate(ContentTemplateBase):
    id: int
    created_at: str | None = None
    updated_at: str | None = None
