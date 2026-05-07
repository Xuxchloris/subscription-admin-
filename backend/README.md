# Hermes Admin Backend

FastAPI backend for managing Hermes Agent cron jobs through the local Hermes CLI.

Run locally:

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Create the first admin user after installing dependencies:

```powershell
python -c "from app.db.base import Base; from app.db.session import engine, SessionLocal; from app.models.admin_user import AdminUser; from app.models import audit, job_metadata, operation_result; from app.core.security import hash_password; Base.metadata.create_all(bind=engine); db=SessionLocal(); db.add(AdminUser(username='admin', password_hash=hash_password('change-me-now'))); db.commit(); db.close()"
```

Change the username and password before exposing the service.
