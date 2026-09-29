import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.dependencies import get_current_user, require_roles
from app.core.security import create_access_token, hash_password
from app.core.time import ensure_utc, utcnow
from app.db.database import get_db
from app.db.models.judge import Judge, JudgeAssignment, JudgeInvite
from app.db.models.project import Project, ProjectStatus
from app.db.models.project_judging import Criterion, Rubric, Score
from app.db.models.user import User, UserRole
from app.schemas.auth import TokenResponse, UserResponse
from app.schemas.judge import (
    JudgeAcceptInvite,
    JudgeAssignmentCreate,
    JudgeAssignmentOut,
    JudgeAssignmentView,
    JudgeInviteCreate,
    JudgeInviteOut,
    JudgeOut,
)
from app.services.audit import write_audit


router = APIRouter(prefix="/api/judges", tags=["Judges"])


def active_rubric(db: Session, event_id: int) -> Rubric | None:
    return db.scalar(
        select(Rubric)
        .options(joinedload(Rubric.criteria))
        .where(Rubric.event_id == event_id, Rubric.active.is_(True))
        .order_by(Rubric.id.desc())
    )


def completed_review_count(db: Session, judge_id: int, project_id: int, rubric: Rubric | None) -> bool:
    if not rubric or not rubric.criteria:
        return False
    scored = db.scalar(
        select(func.count(Score.id)).where(
            Score.judge_id == judge_id,
            Score.project_id == project_id,
        )
    ) or 0
    return scored == len(rubric.criteria)


@router.get("", response_model=list[JudgeOut])
def list_judges(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ORGANIZER, UserRole.ADMIN)),
):
    judges = db.scalars(
        select(Judge).options(joinedload(Judge.user)).order_by(Judge.id)
    ).all()

    output = []
    for judge in judges:
        assignments = db.scalars(
            select(JudgeAssignment)
            .join(JudgeAssignment.project)
            .where(JudgeAssignment.judge_id == judge.id)
        ).all()
        completed = 0
        for assignment in assignments:
            rubric = active_rubric(db, assignment.project.event_id)
            if completed_review_count(db, judge.id, assignment.project_id, rubric):
                completed += 1
        output.append(
            JudgeOut(
                id=judge.id,
                user_id=judge.user_id,
                name=judge.user.name,
                email=judge.user.email,
                assigned_count=len(assignments),
                completed_count=completed,
            )
        )
    return output


@router.post("/invitations", response_model=JudgeInviteOut, status_code=status.HTTP_201_CREATED)
def invite_judge(
    payload: JudgeInviteCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ORGANIZER, UserRole.ADMIN)),
):
    email = payload.email.strip().lower()

    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="A user with this email already exists")

    existing_invite = db.scalar(
        select(JudgeInvite).where(
            JudgeInvite.email == email,
            JudgeInvite.accepted.is_(False),
        )
    )
    if existing_invite and ensure_utc(existing_invite.expires_at) > utcnow():
        raise HTTPException(status_code=409, detail="An active invitation already exists")

    invite = JudgeInvite(
        email=email,
        token=secrets.token_urlsafe(32),
        created_by=user.id,
        expires_at=utcnow() + timedelta(hours=72),
        accepted=False,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    write_audit(db, user.id, "judge.invite.create", "judge_invite", invite.id)
    db.commit()

    return JudgeInviteOut(
        email=invite.email,
        token=invite.token,
        invite_url=f"/join/judge/{invite.token}",
        expires_at=ensure_utc(invite.expires_at).isoformat(),
    )


@router.post("/accept-invite", response_model=TokenResponse)
def accept_judge_invite(
    payload: JudgeAcceptInvite,
    db: Session = Depends(get_db),
):
    invite = db.scalar(
        select(JudgeInvite).where(
            JudgeInvite.token == payload.token,
            JudgeInvite.accepted.is_(False),
        )
    )
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found or already used")
    if ensure_utc(invite.expires_at) < utcnow():
        raise HTTPException(status_code=410, detail="Invite expired")

    email = invite.email.strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="A user with this email already exists")

    user = User(
        name=payload.name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
        role=UserRole.JUDGE,
    )
    db.add(user)
    db.flush()

    db.add(Judge(user_id=user.id))
    invite.accepted = True
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.role.value)
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user, from_attributes=True),
    )


@router.post("/assign", response_model=list[JudgeAssignmentOut])
def assign_judges(
    payload: JudgeAssignmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ORGANIZER, UserRole.ADMIN)),
):
    if payload.strategy not in {"round_robin", "all"}:
        raise HTTPException(status_code=400, detail="Strategy must be 'round_robin' or 'all'")

    judges = [db.get(Judge, judge_id) for judge_id in payload.judge_ids]
    projects = [db.get(Project, project_id) for project_id in payload.project_ids]
    if any(judge is None for judge in judges):
        raise HTTPException(status_code=404, detail="One or more judges were not found")
    if any(project is None for project in projects):
        raise HTTPException(status_code=404, detail="One or more projects were not found")
    if any(project.status != ProjectStatus.SUBMITTED for project in projects):
        raise HTTPException(status_code=400, detail="Only submitted projects can be assigned")

    created: list[JudgeAssignment] = []
    if payload.strategy == "round_robin":
        for index, project in enumerate(projects):
            judge = judges[index % len(judges)]
            existing = db.scalar(
                select(JudgeAssignment).where(
                    JudgeAssignment.judge_id == judge.id,
                    JudgeAssignment.project_id == project.id,
                )
            )
            if existing:
                continue
            assignment = JudgeAssignment(judge_id=judge.id, project_id=project.id)
            db.add(assignment)
            created.append(assignment)
    else:
        for project in projects:
            for judge in judges:
                existing = db.scalar(
                    select(JudgeAssignment).where(
                        JudgeAssignment.judge_id == judge.id,
                        JudgeAssignment.project_id == project.id,
                    )
                )
                if existing:
                    continue
                assignment = JudgeAssignment(judge_id=judge.id, project_id=project.id)
                db.add(assignment)
                created.append(assignment)

    db.commit()
    for assignment in created:
        write_audit(
            db,
            user.id,
            "judge.assign",
            "assignment",
            assignment.id,
            {"judge_id": assignment.judge_id, "project_id": assignment.project_id},
        )
    db.commit()

    return [
        JudgeAssignmentOut(
            id=assignment.id,
            judge_id=assignment.judge_id,
            project_id=assignment.project_id,
            assigned_at=ensure_utc(assignment.assigned_at).isoformat(),
        )
        for assignment in created
    ]


@router.get("/assignments", response_model=list[JudgeAssignmentView])
def get_assignments(
    judge_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role == UserRole.JUDGE:
        judge = db.scalar(select(Judge).where(Judge.user_id == user.id))
        if not judge:
            raise HTTPException(status_code=404, detail="Judge profile not found")
        requested_judge_id = judge.id
    elif user.role in {UserRole.ORGANIZER, UserRole.ADMIN}:
        requested_judge_id = judge_id
    else:
        raise HTTPException(status_code=403, detail="You cannot view judge assignments")

    query = (
        select(JudgeAssignment)
        .join(JudgeAssignment.judge)
        .join(JudgeAssignment.project)
        .options(
            joinedload(JudgeAssignment.judge).joinedload(Judge.user),
            joinedload(JudgeAssignment.project).joinedload(Project.team),
            joinedload(JudgeAssignment.project).joinedload(Project.track),
        )
        .order_by(JudgeAssignment.id)
    )
    if requested_judge_id is not None:
        query = query.where(JudgeAssignment.judge_id == requested_judge_id)

    assignments = db.scalars(query).unique().all()
    output = []
    for assignment in assignments:
        project = assignment.project
        rubric = active_rubric(db, project.event_id)
        scores_required = len(rubric.criteria) if rubric else 0
        scores_completed = db.scalar(
            select(func.count(Score.id)).where(
                Score.judge_id == assignment.judge_id,
                Score.project_id == assignment.project_id,
            )
        ) or 0
        output.append(
            JudgeAssignmentView(
                id=assignment.id,
                judge_id=assignment.judge_id,
                judge_name=assignment.judge.user.name,
                project_id=assignment.project_id,
                project_title=project.title,
                project_summary=project.summary,
                team_name=project.team.name if project.team else None,
                track_name=project.track.name if project.track else None,
                repo_url=project.repo_url,
                demo_url=project.demo_url,
                event_id=project.event_id,
                rubric_id=rubric.id if rubric else None,
                completed=(scores_required > 0 and scores_completed == scores_required),
                scores_completed=scores_completed,
                scores_required=scores_required,
                assigned_at=ensure_utc(assignment.assigned_at).isoformat(),
            )
        )
    return output
