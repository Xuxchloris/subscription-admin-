from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.api import audit, auth, customers, health, jobs, subscriptions, templates
from app.db.base import Base
from app.db.migrations import ensure_job_metadata_columns
from app.db.session import engine
from app.models import admin_user, audit as audit_model, content_template, customer, job_metadata, operation_result, subscription
from app.schemas.common import ok

app = FastAPI(title="Hermes Admin API")
app.include_router(auth.router)
app.include_router(auth.me_router)
app.include_router(health.router)
app.include_router(customers.router)
app.include_router(subscriptions.router)
app.include_router(jobs.router)
app.include_router(templates.router)
app.include_router(audit.router)

Base.metadata.create_all(bind=engine)
ensure_job_metadata_columns(engine)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = (
        exc.detail
        if isinstance(exc.detail, dict)
        else {"code": "HTTP_ERROR", "message": str(exc.detail)}
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "data": None, "error": detail},
    )


@app.get("/api/health/ping")
def ping() -> dict:
    return ok({"status": "ok"})
