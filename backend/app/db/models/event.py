from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submission_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    tracks = relationship("Track", back_populates="event", cascade="all, delete-orphan")
    prizes = relationship("Prize", back_populates="event", cascade="all, delete-orphan")
    teams = relationship("Team", back_populates="event", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="event", cascade="all, delete-orphan")
    rubrics = relationship("Rubric", back_populates="event", cascade="all, delete-orphan")
    community_vote_config = relationship("CommunityVoteConfig", back_populates="event", uselist=False, cascade="all, delete-orphan")


class Track(Base):
    __tablename__ = "tracks"
    __table_args__ = (UniqueConstraint("event_id", "name", name="uq_track_event_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    event = relationship("Event", back_populates="tracks")
    projects = relationship("Project", back_populates="track")


class Prize(Base):
    __tablename__ = "prizes"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[float | None] = mapped_column(Float)
    rank: Mapped[int | None] = mapped_column(Integer)

    event = relationship("Event", back_populates="prizes")
