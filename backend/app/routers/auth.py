from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.database import get_db
from app.db.models.user import User, UserRole
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)


@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(
    credentials: LoginRequest,
    db: Session = Depends(get_db),
):
    stmt = select(User).where(User.email == credentials.email.lower())
    user = db.scalar(stmt)

    if not user or not verify_password(
        credentials.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token(
        user_id=user.id,
        role=user.role.value,
    )

    return TokenResponse(
        access_token=token,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
):
    email = payload.email.strip().lower()
    name = payload.name.strip()

    existing = db.scalar(select(User).where(User.email == email))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    user = User(
        name=name,
        email=email,
        password_hash=hash_password(payload.password),
        role=UserRole.PARTICIPANT,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get(
    "/me",
    response_model=UserResponse,
)
def get_me(
    current_user: User = Depends(get_current_user),
):
    return current_user


@router.post("/logout")
def logout(
    current_user: User = Depends(get_current_user),
):
    # JWT access tokens are stateless.
    # The frontend should delete the token after this request.
    return {
        "message": "Logged out successfully",
    }