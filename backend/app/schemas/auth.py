from pydantic import BaseModel, ConfigDict, Field

from app.db.models.user import UserRole


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=72)


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: UserRole

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse | None = None
