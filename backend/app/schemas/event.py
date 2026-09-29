from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def validate_non_empty(value: str) -> str:
    value = value.strip()

    if not value:
        raise ValueError("Value cannot be empty")

    return value


class TrackCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return validate_non_empty(value)


class TrackOut(BaseModel):
    id: int
    event_id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class PrizeCreate(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=1000)
    amount: float | None = Field(default=None, ge=0)
    rank: int | None = Field(default=None, ge=1)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return validate_non_empty(value)


class PrizeOut(BaseModel):
    id: int
    event_id: int
    title: str
    description: str | None
    amount: float | None
    rank: int | None

    model_config = ConfigDict(from_attributes=True)


class EventCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    start_date: datetime
    end_date: datetime
    submission_deadline: datetime

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return validate_non_empty(value)


class EventUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    start_date: datetime | None = None
    end_date: datetime | None = None
    submission_deadline: datetime | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None

        return validate_non_empty(value)


class EventOut(BaseModel):
    id: int
    name: str
    description: str | None
    start_date: datetime
    end_date: datetime
    submission_deadline: datetime
    status: str

    tracks: list[TrackOut] = Field(default_factory=list)
    prizes: list[PrizeOut] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)