from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")

    if len(password_bytes) > 72:
        raise ValueError("Password is too long for bcrypt (maximum 72 bytes).")

    return bcrypt.hashpw(
        password_bytes,
        bcrypt.gensalt()
    ).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    password_bytes = plain_password.encode("utf-8")

    if len(password_bytes) > 72:
        return False

    try:
        return bcrypt.checkpw(
            password_bytes,
            password_hash.encode("utf-8")
        )
    except (ValueError, TypeError):
        return False


def create_access_token(
    user_id: int,
    role: str,
    expires_minutes: int | None = None,
) -> str:
    minutes = (
        expires_minutes
        if expires_minutes is not None
        else settings.access_token_expire_minutes
    )

    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)

    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc