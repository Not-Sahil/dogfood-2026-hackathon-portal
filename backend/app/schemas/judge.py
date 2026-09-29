from pydantic import BaseModel, Field


class JudgeInviteCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)


class JudgeInviteOut(BaseModel):
    email: str
    token: str
    invite_url: str
    expires_at: str


class JudgeOut(BaseModel):
    id: int
    user_id: int
    name: str
    email: str
    assigned_count: int = 0
    completed_count: int = 0


class JudgeAcceptInvite(BaseModel):
    token: str = Field(min_length=10, max_length=128)
    name: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=8, max_length=72)


class JudgeAssignmentCreate(BaseModel):
    judge_ids: list[int] = Field(min_length=1)
    project_ids: list[int] = Field(min_length=1)
    strategy: str = Field(default="round_robin")


class JudgeAssignmentOut(BaseModel):
    id: int
    judge_id: int
    project_id: int
    assigned_at: str


class JudgeAssignmentView(BaseModel):
    id: int
    judge_id: int
    judge_name: str
    project_id: int
    project_title: str
    project_summary: str = ""
    team_name: str | None = None
    track_name: str | None = None
    repo_url: str | None = None
    demo_url: str | None = None
    event_id: int
    rubric_id: int | None = None
    completed: bool = False
    scores_completed: int = 0
    scores_required: int = 0
    assigned_at: str
