from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models.admin_user import AdminUser


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def authenticate(self, username: str, password: str) -> str | None:
        user = self.db.query(AdminUser).filter_by(username=username).one_or_none()
        if user is None:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return create_access_token(user.username)

    def change_password(self, username: str, current_password: str, new_password: str) -> bool:
        user = self.db.query(AdminUser).filter_by(username=username).one_or_none()
        if user is None:
            return False
        if not verify_password(current_password, user.password_hash):
            return False
        user.password_hash = hash_password(new_password)
        self.db.commit()
        return True
