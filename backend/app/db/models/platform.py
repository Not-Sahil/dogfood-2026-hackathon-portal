from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class CommunityVoteConfig(Base):
    __tablename__ = "community_vote_configs"
    __table_args__ = (UniqueConstraint("event_id", name="uq_vote_config_event"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    voting_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    voting_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    results_hidden_until_close: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    max_votes_per_user: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    event = relationship("Event", back_populates="community_vote_config")


class CommunityVote(Base):
    __tablename__ = "community_votes"
    __table_args__ = (
        UniqueConstraint("event_id", "voter_user_id", "project_id", name="uq_community_vote"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    voter_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    voter_ip_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)

    event = relationship("Event")
    voter = relationship("User")
    project = relationship("Project")


class CommunityComment(Base):
    __tablename__ = "community_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    author_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)

    event = relationship("Event")
    project = relationship("Project")
    author = relationship("User")


class PairwiseComparison(Base):
    __tablename__ = "pairwise_comparisons"
    __table_args__ = (
        UniqueConstraint("event_id", "judge_id", "project_low_id", "project_high_id", name="uq_pairwise_judge_pair"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    judge_id: Mapped[int] = mapped_column(ForeignKey("judges.id", ondelete="CASCADE"), index=True)
    project_low_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    project_high_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    winner_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    event = relationship("Event")
    judge = relationship("Judge")
    project_low = relationship("Project", foreign_keys=[project_low_id])
    project_high = relationship("Project", foreign_keys=[project_high_id])
    winner = relationship("Project", foreign_keys=[winner_id])


class WebhookEndpoint(Base):
    __tablename__ = "webhook_endpoints"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True, nullable=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    secret: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class JudgeRecord(Base):
    __tablename__ = "judge_records"
    __table_args__ = (UniqueConstraint("judge_id", "event_id", name="uq_judge_record"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    judge_id: Mapped[int] = mapped_column(ForeignKey("judges.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    signature: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
