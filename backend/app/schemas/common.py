from typing import Any

from pydantic import BaseModel, Field


class ApiError(BaseModel):
    code: str
    message: str
    operation: str | None = None
    hermes_output: str | None = None
    suggested_checks: list[str] = Field(default_factory=list)


class ApiResponse(BaseModel):
    success: bool
    data: Any | None = None
    error: ApiError | None = None


def ok(data: Any) -> dict[str, Any]:
    return ApiResponse(success=True, data=data, error=None).model_dump()


def fail(error: ApiError) -> dict[str, Any]:
    return ApiResponse(success=False, data=None, error=error).model_dump()
