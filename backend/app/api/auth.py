from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.auth import ChangePasswordRequest, LoginRequest, LoginResponse
from app.schemas.common import ApiError, ok
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict:
    token = AuthService(db).authenticate(payload.username, payload.password)
    if token is None:
        error = ApiError(code="INVALID_CREDENTIALS", message="Invalid username or password.")
        raise HTTPException(status_code=401, detail=error.model_dump())
    return ok(LoginResponse(access_token=token).model_dump())


@router.post("/logout")
def logout() -> dict:
    return ok({"status": "logged_out"})


def _current_admin(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> str:
    return require_admin(credentials)


@router.post("/password")
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    subject: str = Depends(_current_admin),
) -> dict:
    changed = AuthService(db).change_password(subject, payload.current_password, payload.new_password)
    if not changed:
        error = ApiError(code="INVALID_CREDENTIALS", message="Invalid current password.")
        return {"success": False, "data": None, "error": error.model_dump()}
    return ok({"status": "password_changed"})


def require_admin(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> str:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "AUTH_REQUIRED", "message": "Authentication required."},
        )
    settings = get_settings()
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail={"code": "AUTH_REQUIRED", "message": "Authentication required."},
        ) from None
    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise HTTPException(
            status_code=401,
            detail={"code": "AUTH_REQUIRED", "message": "Authentication required."},
        )
    return subject


me_router = APIRouter(prefix="/api", tags=["auth"])


@me_router.get("/me")
def me(subject: str = Depends(require_admin)) -> dict:
    return ok({"username": subject})
