from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api import auth as auth_api
from app.core.security import hash_password, verify_password
from app.db.base import Base
from app.main import app
from app.models.admin_user import AdminUser


def test_login_rejects_bad_credentials():
    client = TestClient(app)
    response = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})

    assert response.status_code == 401
    assert response.json()["success"] is False
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_change_password_requires_current_password_and_updates_hash():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(AdminUser(username="admin", password_hash=hash_password("old-secret")))
        session.commit()

        bad_response = auth_api.change_password(
            auth_api.ChangePasswordRequest(current_password="wrong", new_password="new-secret"),
            db=session,
            subject="admin",
        )
        assert bad_response["success"] is False

        response = auth_api.change_password(
            auth_api.ChangePasswordRequest(current_password="old-secret", new_password="new-secret"),
            db=session,
            subject="admin",
        )
        user = session.query(AdminUser).filter_by(username="admin").one()

    assert response["success"] is True
    assert verify_password("new-secret", user.password_hash)
