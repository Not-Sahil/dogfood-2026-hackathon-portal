from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Rubric(Base):
    __tablename__ = "rubrics"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    event_id: Mapped[int] = mapped_column(
        ForeignKey(
            "events.id",
            ondelete="CASCADE",
        ),
        index=True,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
        index=True,
    )

    event = relationship(
        "Event",
        back_populates="rubrics",
    )

    criteria = relationship(
        "Criterion",
        back_populates="rubric",
        cascade="all, delete-orphan",
        order_by="Criterion.id",
    )


class Criterion(Base):
    __tablename__ = "criteria"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    rubric_id: Mapped[int] = mapped_column(
        ForeignKey(
            "rubrics.id",
            ondelete="CASCADE",
        ),
        index=True,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    weight: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    max_score: Mapped[float] = mapped_column(
        Float,
        default=5.0,
        nullable=False,
    )

    rubric = relationship(
        "Rubric",
        back_populates="criteria",
    )

    scores = relationship(
        "Score",
        back_populates="criterion",
        cascade="all, delete-orphan",
    )


class Score(Base):
    __tablename__ = "scores"

    __table_args__ = (
        UniqueConstraint(
            "judge_id",
            "project_id",
            "criterion_id",
            name="uq_score_judge_project_criterion",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    judge_id: Mapped[int] = mapped_column(
        ForeignKey(
            "judges.id",
            ondelete="CASCADE",
        ),
        index=True,
        nullable=False,
    )

    project_id: Mapped[int] = mapped_column(
        ForeignKey(
            "projects.id",
            ondelete="CASCADE",
        ),
        index=True,
        nullable=False,
    )

    criterion_id: Mapped[int] = mapped_column(
        ForeignKey(
            "criteria.id",
            ondelete="CASCADE",
        ),
        index=True,
        nullable=False,
    )

    score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    comment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    judge = relationship(
        "Judge",
        back_populates="scores",
    )

    project = relationship(
        "Project",
        back_populates="scores",
    )

    criterion = relationship(
        "Criterion",
        back_populates="scores",
    )