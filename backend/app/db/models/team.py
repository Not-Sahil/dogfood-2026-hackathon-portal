from datetime import datetime, timedelta, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    event = relationship(
        "Event",
        back_populates="teams",
    )

    members = relationship(
        "TeamMember",
        back_populates="team",
        cascade="all, delete-orphan",
    )

    invites = relationship(
        "TeamInvite",
        back_populates="team",
        cascade="all, delete-orphan",
    )

    projects = relationship(
        "Project",
        back_populates="team",
    )


class TeamMember(Base):
    __tablename__ = "team_members"

    __table_args__ = (
        UniqueConstraint(
            "team_id",
            "user_id",
            name="uq_team_member",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    is_captain: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    team = relationship(
        "Team",
        back_populates="members",
    )

    user = relationship(
        "User",
        back_populates="team_memberships",
    )


class TeamInvite(Base):
    __tablename__ = "team_invites"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    token: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        index=True,
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
        + timedelta(hours=48),
        nullable=False,
    )

    used: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    team = relationship(
        "Team",
        back_populates="invites",
    )