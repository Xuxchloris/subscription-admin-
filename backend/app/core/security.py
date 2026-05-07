from datetime import datetime, timedelta, timezone
import base64
import hashlib

import bcrypt
from jose import jwt

from app.core.config import get_settings

PASSWORD_HASH_PREFIX = "sha256_bcrypt$"


def _password_bytes(password: str) -> bytes:
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt())
    return f"{PASSWORD_HASH_PREFIX}{hashed.decode('utf-8')}"


def verify_password(password: str, password_hash: str) -> bool:
    if password_hash.startswith(PASSWORD_HASH_PREFIX):
        raw_hash = password_hash.removeprefix(PASSWORD_HASH_PREFIX).encode("utf-8")
        return bcrypt.checkpw(_password_bytes(password), raw_hash)
    raw_password = password.encode("utf-8")
    if len(raw_password) > 72:
        return False
    return bcrypt.checkpw(raw_password, password_hash.encode("utf-8"))


def create_access_token(subject: str) -> str:
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    payload = {"sub": subject, "exp": expires}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
