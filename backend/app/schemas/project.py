from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def clean_text(value: str) -> str:
    value = value.strip()

    if not value:
        raise ValueError("Value cannot be empty")

    return value


class ProjectCreate(BaseModel):
    event_id: int = Field(gt=0)
    team_id: int = Field(gt=0)
    track_id: int = Field(gt=0)

    title: str = Field(
        min_length=2,
        max_length=200,
    )

    summary: str = Field(
        min_length=10,
        max_length=10000,
    )

    repo_url: str | None = Field(
        default=None,
        max_length=500,
    )

    demo_url: str | None = Field(
        default=None,
        max_length=500,
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return clean_text(value)

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, value: str) -> str:
        return clean_text(value)

    @field_validator("repo_url", "demo_url")
    @classmethod
    def validate_urls(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip()

        if not value:
            return None

        return value


class ProjectUpdate(BaseModel):
    title: str | None = Field(
        default=None,
        min_length=2,
        max_length=200,
    )

    summary: str | None = Field(
        default=None,
        min_length=10,
        max_length=10000,
    )

    track_id: int | None = Field(
        default=None,
        gt=0,
    )

    repo_url: str | None = Field(
        default=None,
        max_length=500,
    )

    demo_url: str | None = Field(
        default=None,
        max_length=500,
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is None:
            return None

        return clean_text(value)

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, value: str | None) -> str | None:
        if value is None:
            return None

        return clean_text(value)

    @field_validator("repo_url", "demo_url")
    @classmethod
    def validate_urls(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip()

        if not value:
            return None

        return value


class SubmissionOut(BaseModel):
    id: int
    project_id: int
    submitted_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


class ProjectOut(BaseModel):
    id: int
    event_id: int
    team_id: int
    track_id: int

    title: str
    summary: str

    repo_url: str | None
    demo_url: str | None

    status: str

    created_at: datetime
    updated_at: datetime

    team_name: str | None = None
    team_size: int | None = None
    track_name: str | None = None
    submission: SubmissionOut | None = None

    model_config = ConfigDict(
        from_attributes=True,
    )