from datetime import datetime
from pydantic import BaseModel, Field


class CommunityConfigIn(BaseModel):
    event_id: int = Field(gt=0)
    voting_start: datetime
    voting_end: datetime
    results_hidden_until_close: bool = True
    max_votes_per_user: int = Field(default=5, ge=1, le=100)
    active: bool = True


class CommunityConfigOut(CommunityConfigIn):
    id: int


class CommunityVoteIn(BaseModel):
    event_id: int = Field(gt=0)
    project_id: int = Field(gt=0)


class CommunityCommentIn(BaseModel):
    event_id: int = Field(gt=0)
    project_id: int = Field(gt=0)
    body: str = Field(min_length=1, max_length=2000)


class PairwiseVoteIn(BaseModel):
    event_id: int = Field(gt=0)
    project_a_id: int = Field(gt=0)
    project_b_id: int = Field(gt=0)
    winner_id: int = Field(gt=0)


class WebhookCreate(BaseModel):
    event_id: int | None = Field(default=None, gt=0)
    url: str = Field(min_length=8, max_length=500)
    secret: str = Field(min_length=8, max_length=255)


class WebhookOut(BaseModel):
    id: int
    event_id: int | None
    url: str
    active: bool
    created_at: datetime


class BulkImportResult(BaseModel):
    imported: int
    skipped: int
    errors: list[str] = Field(default_factory=list)
