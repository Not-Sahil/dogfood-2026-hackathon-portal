from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Judge(Base):
    __tablename__ = "judges"
    __table_args__ = (UniqueConstraint("user_id", name="uq_judge_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    invited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    user = relationship("User", back_populates="judge_profile")
    assignments = relationship("JudgeAssignment", back_populates="judge", cascade="all, delete-orphan")
    scores = relationship("Score", back_populates="judge", cascade="all, delete-orphan")


class JudgeInvite(Base):
    __tablename__ = "judge_invites"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class JudgeAssignment(Base):
    __tablename__ = "judge_assignments"
    __table_args__ = (UniqueConstraint("judge_id", "project_id", name="uq_judge_project_assignment"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    judge_id: Mapped[int] = mapped_column(ForeignKey("judges.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    judge = relationship("Judge", back_populates="assignments")
    project = relationship("Project", back_populates="assignments")
