from pydantic import BaseModel, Field


class JudgeBreakdown(BaseModel):
    judge_id: int
    judge_name: str
    raw_score: float | None = None
    normalized_score: float | None = None
    judge_mean: float | None = None
    judge_std: float | None = None
    note: str | None = None


class NormalizationInfo(BaseModel):
    method: str
    scale: str
    panel_mean: float
    panel_std: float
    explanation: str


class ResultRow(BaseModel):
    rank_raw: int | None = None
    rank_normalized: int | None = None
    project_id: int
    project_title: str
    team_name: str | None = None
    track_name: str | None = None
    raw_score: float | None = None
    normalized_score: float | None = None
    completed_reviews: int
    assigned_reviews: int
    rank_change: int | None = None
    judge_breakdown: list[JudgeBreakdown] = Field(default_factory=list)


class IntegritySummary(BaseModel):
    total_reviews: int
    completed_reviews: int
    pending_reviews: int
    judge_anomalies: int
    projects_with_incomplete_reviews: int


class ResultResponse(BaseModel):
    event_id: int
    normalization: NormalizationInfo
    rows: list[ResultRow] = Field(default_factory=list)
    integrity: IntegritySummary
