from pydantic import BaseModel, Field


class HermesHealth(BaseModel):
    gateway_running: bool
    raw: str
    suggested_checks: list[str] = Field(default_factory=list)
