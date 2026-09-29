import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.dependencies import get_current_user, require_roles
from app.core.time import ensure_utc, utcnow
from app.db.database import get_db
from app.db.models.event import Event
from app.db.models.team import Team, TeamInvite, TeamMember
from app.db.models.user import User, UserRole
from app.schemas.team import (
    InviteOut,
    JoinInviteRequest,
    JoinTeamResponse,
    TeamCreate,
    TeamMemberOut,
    TeamOut,
)
from app.services.audit import write_audit


router = APIRouter(
    prefix="/api/teams",
    tags=["Teams"],
)


def load_team(
    db: Session,
    team_id: int,
) -> Team | None:
    return db.scalar(
        select(Team)
        .options(
            joinedload(Team.members)
            .joinedload(TeamMember.user)
        )
        .where(Team.id == team_id)
    )


def serialize_team(team: Team) -> TeamOut:
    return TeamOut(
        id=team.id,
        event_id=team.event_id,
        name=team.name,
        created_by=team.created_by,
        members=[
            TeamMemberOut(
                user_id=member.user_id,
                name=member.user.name,
                email=member.user.email,
                is_captain=member.is_captain,
            )
            for member in team.members
        ],
    )


def is_team_member(
    db: Session,
    team_id: int,
    user_id: int,
) -> bool:
    return (
        db.scalar(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == user_id,
            )
        )
        is not None
    )


def get_user_event_team(
    db: Session,
    event_id: int,
    user_id: int,
) -> Team | None:
    return db.scalar(
        select(Team)
        .join(TeamMember, TeamMember.team_id == Team.id)
        .where(
            Team.event_id == event_id,
            TeamMember.user_id == user_id,
        )
    )


# ---------------------------------------------------------
# Organizer/admin team directory
# ---------------------------------------------------------

@router.get(
    "",
    response_model=list[TeamOut],
)
def get_all_teams(
    event_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(UserRole.ORGANIZER, UserRole.ADMIN)
    ),
):
    query = (
        select(Team)
        .options(joinedload(Team.members).joinedload(TeamMember.user))
        .order_by(Team.id.desc())
    )
    if event_id is not None:
        query = query.where(Team.event_id == event_id)
    teams = db.scalars(query).unique().all()
    return [serialize_team(team) for team in teams]


# ---------------------------------------------------------
# Create team
# ---------------------------------------------------------

@router.post(
    "",
    response_model=TeamOut,
    status_code=status.HTTP_201_CREATED,
)
def create_team(
    payload: TeamCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != UserRole.PARTICIPANT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only participants can create teams",
        )

    event = db.get(Event, payload.event_id)

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    if ensure_utc(event.submission_deadline) < utcnow():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Team formation is closed for this event",
        )

    # One participant cannot belong to multiple teams
    # within the same event.
    existing_team = get_user_event_team(
        db,
        payload.event_id,
        user.id,
    )

    if existing_team:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"You are already a member of team "
                f"'{existing_team.name}' for this event"
            ),
        )

    team = Team(
        event_id=payload.event_id,
        name=payload.name.strip(),
        created_by=user.id,
    )

    db.add(team)
    db.flush()

    captain = TeamMember(
        team_id=team.id,
        user_id=user.id,
        is_captain=True,
    )

    db.add(captain)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unable to create team",
        ) from exc

    write_audit(
        db,
        user.id,
        "team.create",
        "team",
        team.id,
    )

    db.commit()

    created_team = load_team(
        db,
        team.id,
    )

    if not created_team:
        raise HTTPException(
            status_code=500,
            detail="Team creation failed",
        )

    return serialize_team(created_team)


# ---------------------------------------------------------
# My teams
# ---------------------------------------------------------

@router.get(
    "/my",
    response_model=list[TeamOut],
)
def get_my_teams(
    event_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = (
        select(Team)
        .join(
            TeamMember,
            TeamMember.team_id == Team.id,
        )
        .options(
            joinedload(Team.members)
            .joinedload(TeamMember.user)
        )
        .where(
            TeamMember.user_id == user.id
        )
    )

    if event_id is not None:
        query = query.where(
            Team.event_id == event_id
        )

    teams = db.scalars(
        query.order_by(Team.id.desc())
    ).unique().all()

    return [
        serialize_team(team)
        for team in teams
    ]


# ---------------------------------------------------------
# Get team
# ---------------------------------------------------------

@router.get(
    "/{team_id}",
    response_model=TeamOut,
)
def get_team(
    team_id: int,
    db: Session = Depends(get_db),
):
    team = load_team(
        db,
        team_id,
    )

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    return serialize_team(team)


# ---------------------------------------------------------
# Create invite
# ---------------------------------------------------------

@router.post(
    "/{team_id}/invites",
    response_model=InviteOut,
    status_code=status.HTTP_201_CREATED,
)
def create_invite(
    team_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    team = db.get(Team, team_id)

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    if not is_team_member(
        db,
        team_id,
        user.id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only team members can create invites",
        )

    if ensure_utc(
        team.event.submission_deadline
    ) < utcnow():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Team invitations are closed",
        )

    token = secrets.token_urlsafe(32)

    invite = TeamInvite(
        team_id=team_id,
        token=token,
    )

    db.add(invite)
    db.commit()
    db.refresh(invite)

    write_audit(
        db,
        user.id,
        "team.invite.create",
        "team",
        team.id,
    )

    db.commit()

    return InviteOut(
        token=invite.token,
        join_url=f"/join/team/{invite.token}",
        expires_at=invite.expires_at,
    )


# ---------------------------------------------------------
# Join through invite
# ---------------------------------------------------------

@router.post(
    "/join",
    response_model=JoinTeamResponse,
)
def join_team(
    payload: JoinInviteRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != UserRole.PARTICIPANT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only participants can join teams",
        )

    invite = db.scalar(
        select(TeamInvite).where(
            TeamInvite.token == payload.token,
            TeamInvite.used.is_(False),
        )
    )

    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite not found or already used",
        )

    if ensure_utc(invite.expires_at) < utcnow():
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Invite expired",
        )

    team = db.get(Team, invite.team_id)

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    if ensure_utc(
        team.event.submission_deadline
    ) < utcnow():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Team joining is closed",
        )

    # Prevent joining multiple teams in the same event.
    existing_team = get_user_event_team(
        db,
        team.event_id,
        user.id,
    )

    if existing_team:
        if existing_team.id == team.id:
            return JoinTeamResponse(
                message="Already a team member",
                team_id=team.id,
            )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"You are already a member of "
                f"'{existing_team.name}' for this event"
            ),
        )

    member = TeamMember(
        team_id=team.id,
        user_id=user.id,
        is_captain=False,
    )

    db.add(member)

    # This implementation uses one-time invitations.
    invite.used = True

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unable to join team",
        ) from exc

    write_audit(
        db,
        user.id,
        "team.join",
        "team",
        team.id,
    )

    db.commit()

    return JoinTeamResponse(
        message="Joined team successfully",
        team_id=team.id,
    )