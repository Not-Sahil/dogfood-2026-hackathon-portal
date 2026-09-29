from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class ProjectStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    CLOSED = "closed"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id"),
        index=True,
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    repo_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    demo_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    status: Mapped[ProjectStatus] = mapped_column(
        SQLEnum(
            ProjectStatus,
            name="project_status",
        ),
        default=ProjectStatus.DRAFT,
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships

    event = relationship(
        "Event",
        back_populates="projects",
    )

    team = relationship(
        "Team",
        back_populates="projects",
    )

    track = relationship(
        "Track",
        back_populates="projects",
    )

    submission = relationship(
        "Submission",
        back_populates="project",
        uselist=False,
        cascade="all, delete-orphan",
    )

    assignments = relationship(
        "JudgeAssignment",
        back_populates="project",
        cascade="all, delete-orphan",
    )

    scores = relationship(
        "Score",
        back_populates="project",
        cascade="all, delete-orphan",
    )


class Submission(Base):
    __tablename__ = "submissions"

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            name="uq_submission_project",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    project_id: Mapped[int] = mapped_column(
        ForeignKey(
            "projects.id",
            ondelete="CASCADE",
        ),
        index=True,
        nullable=False,
    )

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    project = relationship(
        "Project",
        back_populates="submission",
    )