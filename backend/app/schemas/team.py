from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TeamCreate(BaseModel):
    event_id: int
    name: str = Field(
        min_length=2,
        max_length=120,
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()

        if len(value) < 2:
            raise ValueError("Team name must contain at least 2 characters")

        return value


class TeamMemberOut(BaseModel):
    user_id: int
    name: str
    email: str
    is_captain: bool

    model_config = ConfigDict(
        from_attributes=True
    )


class TeamOut(BaseModel):
    id: int
    event_id: int
    name: str
    created_by: int
    members: list[TeamMemberOut] = Field(
        default_factory=list
    )

    model_config = ConfigDict(
        from_attributes=True
    )


class InviteOut(BaseModel):
    token: str
    join_url: str
    expires_at: datetime


class JoinInviteRequest(BaseModel):
    token: str = Field(
        min_length=10,
        max_length=128,
    )


class JoinTeamResponse(BaseModel):
    message: str
    team_id: int