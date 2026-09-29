from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.dependencies import get_current_user, get_optional_user
from app.core.time import ensure_utc, utcnow
from app.db.database import get_db
from app.db.models.event import Event, Track
from app.db.models.project import Project, ProjectStatus, Submission
from app.db.models.team import Team, TeamMember
from app.db.models.user import User, UserRole
from app.schemas.project import ProjectCreate, ProjectOut, ProjectUpdate
from app.services.audit import write_audit
from app.services.webhooks import dispatch_webhook


router = APIRouter(
    prefix="/api/projects",
    tags=["Projects"],
)


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def event_open(event: Event) -> bool:
    """
    Project creation, editing and submission are allowed
    only before the submission deadline.
    """
    return utcnow() < ensure_utc(event.submission_deadline)


def get_project(
    db: Session,
    project_id: int,
) -> Project | None:
    return db.scalar(
        select(Project)
        .options(
            joinedload(Project.submission),
            joinedload(Project.team).joinedload(Team.members),
            joinedload(Project.track),
        )
        .where(Project.id == project_id)
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


def can_manage_project(
    db: Session,
    project: Project,
    user: User,
) -> bool:
    # Organizer/admin can manage projects.
    if user.role in {
        UserRole.ORGANIZER,
        UserRole.ADMIN,
    }:
        return True

    # Participants can manage projects belonging
    # to teams they are members of.
    if user.role != UserRole.PARTICIPANT:
        return False

    return is_team_member(
        db,
        project.team_id,
        user.id,
    )


def serialize_project(project: Project) -> ProjectOut:
    return ProjectOut(
        id=project.id,
        event_id=project.event_id,
        team_id=project.team_id,
        track_id=project.track_id,
        title=project.title,
        summary=project.summary,
        repo_url=project.repo_url,
        demo_url=project.demo_url,
        status=project.status.value,
        created_at=project.created_at,
        updated_at=project.updated_at,
        team_name=project.team.name if project.team else None,
        team_size=len(project.team.members) if project.team and project.team.members is not None else None,
        track_name=project.track.name if project.track else None,
        submission=project.submission,
    )


# ---------------------------------------------------------
# Public gallery / search
# ---------------------------------------------------------

@router.get(
    "",
    response_model=list[ProjectOut],
)
def gallery(
    q: str | None = Query(
        default=None,
        max_length=100,
    ),
    track_id: int | None = Query(
        default=None,
        gt=0,
    ),
    event_id: int | None = Query(
        default=None,
        gt=0,
    ),
    db: Session = Depends(get_db),
):
    """
    Public gallery.

    Only submitted projects are visible publicly.
    """

    query = (
        select(Project)
        .options(
            joinedload(Project.submission),
            joinedload(Project.team).joinedload(Team.members),
            joinedload(Project.track),
        )
        .where(
            Project.status == ProjectStatus.SUBMITTED
        )
    )

    if event_id is not None:
        query = query.where(
            Project.event_id == event_id
        )

    if track_id is not None:
        query = query.where(
            Project.track_id == track_id
        )

    if q:
        term = f"%{q.strip()}%"

        query = query.where(
            or_(
                Project.title.ilike(term),
                Project.summary.ilike(term),
            )
        )

    projects = db.scalars(
        query.order_by(Project.id.desc())
    ).unique().all()

    return [serialize_project(project) for project in projects]


# ---------------------------------------------------------
# Create project / draft
# ---------------------------------------------------------

@router.post(
    "",
    response_model=ProjectOut,
    status_code=status.HTTP_201_CREATED,
)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Only participants should create projects.
    if user.role != UserRole.PARTICIPANT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only participants can create projects",
        )

    event = db.get(
        Event,
        payload.event_id,
    )

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    if not event_open(event):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Submissions are closed",
        )

    team = db.get(
        Team,
        payload.team_id,
    )

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    # CRITICAL: team must belong to the same event.
    if team.event_id != event.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team does not belong to this event",
        )

    if not is_team_member(
        db,
        team.id,
        user.id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this team",
        )

    track = db.get(
        Track,
        payload.track_id,
    )

    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )

    if track.event_id != event.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Track does not belong to this event",
        )

    project = Project(
        event_id=event.id,
        team_id=team.id,
        track_id=track.id,
        title=payload.title.strip(),
        summary=payload.summary.strip(),
        repo_url=payload.repo_url,
        demo_url=payload.demo_url,
        status=ProjectStatus.DRAFT,
    )

    db.add(project)
    db.commit()
    db.refresh(project)

    write_audit(
        db,
        user.id,
        "project.create",
        "project",
        project.id,
    )

    db.commit()

    return serialize_project(project)


# ---------------------------------------------------------
# My projects
# ---------------------------------------------------------

@router.get(
    "/mine",
    response_model=list[ProjectOut],
)
def my_projects(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Returns projects belonging to teams
    the current participant is part of.
    """

    query = (
        select(Project)
        .join(
            TeamMember,
            TeamMember.team_id == Project.team_id,
        )
        .options(
            joinedload(Project.submission),
            joinedload(Project.team).joinedload(Team.members),
            joinedload(Project.track),
        )
        .where(
            TeamMember.user_id == user.id
        )
        .order_by(Project.id.desc())
    )

    projects = db.scalars(query).unique().all()
    return [serialize_project(project) for project in projects]


# ---------------------------------------------------------
# Get project
# ---------------------------------------------------------

@router.get(
    "/{project_id}",
    response_model=ProjectOut,
)
def get_project_by_id(
    project_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """
    Public:
        Can see submitted projects.

    Authenticated owner/organizer/admin:
        Can see drafts too.

    This is necessary for the draft/edit workflow.
    """

    project = get_project(
        db,
        project_id,
    )

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Submitted project is publicly readable.
    if project.status == ProjectStatus.SUBMITTED:
        return serialize_project(project)

    # Draft requires authentication.
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if not can_manage_project(
        db,
        project,
        user,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot access this project",
        )

    return serialize_project(project)


# ---------------------------------------------------------
# Update project / draft
# ---------------------------------------------------------

@router.put(
    "/{project_id}",
    response_model=ProjectOut,
)
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = get_project(
        db,
        project_id,
    )

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if not can_manage_project(
        db,
        project,
        user,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot edit this project",
        )

    event = db.get(
        Event,
        project.event_id,
    )

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    if not event_open(event):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Submissions are closed; project editing is disabled",
        )

    updates = payload.model_dump(
        exclude_unset=True
    )

    # Validate track if changed.
    if "track_id" in updates:
        track = db.get(
            Track,
            updates["track_id"],
        )

        if not track:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Track not found",
            )

        if track.event_id != project.event_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Track does not belong to this event",
            )

    for field, value in updates.items():

        if isinstance(value, str):
            value = value.strip()

        setattr(
            project,
            field,
            value,
        )

    db.commit()
    db.refresh(project)

    write_audit(
        db,
        user.id,
        "project.update",
        "project",
        project.id,
    )

    db.commit()

    return serialize_project(project)


# ---------------------------------------------------------
# Submit project
# ---------------------------------------------------------

@router.post(
    "/{project_id}/submit",
    response_model=ProjectOut,
)
def submit_project(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = get_project(
        db,
        project_id,
    )

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if not can_manage_project(
        db,
        project,
        user,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot submit this project",
        )

    event = db.get(
        Event,
        project.event_id,
    )

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    # Backend-enforced deadline.
    if not event_open(event):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Submissions are closed",
        )

    # Required fields.
    if not project.title.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project title is required",
        )

    if not project.summary.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project summary is required",
        )

    if not project.track_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project track is required",
        )

    # Make sure the project belongs to the correct event.
    track = db.get(
        Track,
        project.track_id,
    )

    if not track or track.event_id != project.event_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project track is invalid",
        )

    # Mark submitted.
    project.status = ProjectStatus.SUBMITTED

    # Create exactly one submission record.
    submission = db.scalar(
        select(Submission).where(
            Submission.project_id == project.id
        )
    )

    if not submission:
        submission = Submission(
            project_id=project.id
        )
        db.add(submission)

    db.commit()

    write_audit(
        db,
        user.id,
        "project.submit",
        "project",
        project.id,
    )

    db.commit()
    dispatch_webhook(db, project.event_id, "project.submit", {"project_id": project.id, "team_id": project.team_id})

    db.refresh(project)

    return serialize_project(project)