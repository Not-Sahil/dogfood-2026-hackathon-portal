from pydantic import BaseModel, ConfigDict, Field, field_validator


class CriterionInput(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=100,
    )

    weight: float = Field(
        gt=0,
        le=100,
    )

    max_score: float = Field(
        default=5.0,
        gt=0,
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError(
                "Criterion name cannot be empty"
            )

        return value


class RubricCreate(BaseModel):
    event_id: int = Field(gt=0)

    name: str = Field(
        min_length=1,
        max_length=150,
    )

    criteria: list[CriterionInput] = Field(
        min_length=1,
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError(
                "Rubric name cannot be empty"
            )

        return value

    @field_validator("criteria")
    @classmethod
    def validate_weights(
        cls,
        value: list[CriterionInput],
    ) -> list[CriterionInput]:

        total = sum(
            item.weight
            for item in value
        )

        if abs(total - 100.0) > 0.01:
            raise ValueError(
                "Criterion weights must total 100%"
            )

        names = [
            item.name.strip().lower()
            for item in value
        ]

        if len(names) != len(set(names)):
            raise ValueError(
                "Criterion names must be unique"
            )

        return value


class CriterionOut(CriterionInput):
    id: int

    model_config = ConfigDict(
        from_attributes=True,
    )


class RubricOut(BaseModel):
    id: int
    event_id: int
    name: str
    active: bool
    criteria: list[CriterionOut]

    model_config = ConfigDict(
        from_attributes=True,
    )


class ScoreInput(BaseModel):
    criterion_id: int

    score: float = Field(
        ge=0,
    )

    comment: str | None = Field(
        default=None,
        max_length=5000,
    )

    @field_validator("comment")
    @classmethod
    def clean_comment(
        cls,
        value: str | None,
    ) -> str | None:

        if value is None:
            return None

        value = value.strip()

        return value or None


class EvaluationCreate(BaseModel):
    project_id: int = Field(gt=0)

    scores: list[ScoreInput] = Field(
        min_length=1,
    )


class ScoreOut(BaseModel):
    criterion_id: int
    score: float
    comment: str | None


class EvaluationOut(BaseModel):
    project_id: int
    judge_id: int
    completed: bool
    raw_score: float
    weighted_score: float
    scores: list[ScoreOut]


class ProgressOut(BaseModel):
    judge_id: int
    name: str
    assigned: int
    completed: int
    pending: int
    completion_percent: float