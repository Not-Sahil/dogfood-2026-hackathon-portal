from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.database import get_db
from app.db.models.user import User, UserRole


bearer_scheme = HTTPBearer(auto_error=False)


def _user_from_credentials(
    credentials: HTTPAuthorizationCredentials | None,
    db: Session,
) -> User | None:
    if not credentials:
        return None

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (ValueError, KeyError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    user = _user_from_credentials(credentials, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    return _user_from_credentials(credentials, db)


def require_roles(*allowed_roles: UserRole) -> Callable:
    def role_dependency(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return role_dependency


def require_participant(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.PARTICIPANT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Participant access required",
        )
    return current_user


def require_judge(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.JUDGE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Judge access required",
        )
    return current_user


def require_organizer(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ORGANIZER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organizer access required",
        )
    return current_user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user
