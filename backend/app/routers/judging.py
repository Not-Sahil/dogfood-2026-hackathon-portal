from collections import defaultdict
from app.db.models.event import Event
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.dependencies import get_current_user, require_roles
from app.core.time import ensure_utc, utcnow
from app.db.database import get_db
from app.db.models.judge import Judge, JudgeAssignment
from app.db.models.project import Project, ProjectStatus
from app.db.models.project_judging import Criterion, Rubric, Score
from app.db.models.user import User, UserRole
from app.schemas.judging import (
    EvaluationCreate,
    EvaluationOut,
    ProgressOut,
    RubricCreate,
    RubricOut,
    ScoreOut,
)
from app.services.audit import write_audit
from app.services.webhooks import dispatch_webhook


router = APIRouter(
    tags=["Judging"],
)


# =========================================================
# Helpers
# =========================================================

def get_judge_for_user(
    db: Session,
    user_id: int,
) -> Judge:
    judge = db.scalar(
        select(Judge).where(
            Judge.user_id == user_id
        )
    )

    if not judge:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Judge profile not found",
        )

    return judge


def get_rubric(
    db: Session,
    rubric_id: int,
) -> Rubric | None:
    return db.scalar(
        select(Rubric)
        .options(
            joinedload(Rubric.criteria)
        )
        .where(
            Rubric.id == rubric_id
        )
    )


def get_active_rubric(
    db: Session,
    event_id: int,
) -> Rubric | None:
    return db.scalar(
        select(Rubric)
        .options(
            joinedload(Rubric.criteria)
        )
        .where(
            Rubric.event_id == event_id,
            Rubric.active.is_(True),
        )
        .order_by(
            Rubric.id.desc()
        )
    )


def calculate_scores(
    scores: list[Score],
    criteria: dict[int, Criterion],
) -> tuple[float, float]:

    if not scores:
        return 0.0, 0.0

    raw_total = sum(
        score.score
        for score in scores
    )

    weighted_total = 0.0

    for score in scores:
        criterion = criteria.get(
            score.criterion_id
        )

        if not criterion:
            continue

        normalized = (
            score.score /
            criterion.max_score
        )

        weighted_total += (
            normalized *
            criterion.weight
        )

    weighted_score = weighted_total / 100.0 * 5.0

    return (
        round(raw_total, 4),
        round(weighted_score, 4),
    )


def evaluation_response(
    project_id: int,
    judge_id: int,
    scores: list[Score],
    criteria: dict[int, Criterion],
) -> EvaluationOut:

    raw_score, weighted_score = calculate_scores(
        scores,
        criteria,
    )

    completed = (
        len(scores)
        == len(criteria)
    )

    return EvaluationOut(
        project_id=project_id,
        judge_id=judge_id,
        completed=completed,
        raw_score=raw_score,
        weighted_score=weighted_score,
        scores=[
            ScoreOut(
                criterion_id=score.criterion_id,
                score=score.score,
                comment=score.comment,
            )
            for score in scores
        ],
    )


# =========================================================
# RUBRICS
# =========================================================

@router.post(
    "/api/rubrics",
    response_model=RubricOut,
    status_code=status.HTTP_201_CREATED,
)
def create_rubric(
    payload: RubricCreate,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(
            UserRole.ORGANIZER,
            UserRole.ADMIN,
        )
    ),
):
    # Event must exist.
    event = db.get(
        Event,
        payload.event_id,
    )

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    # Deactivate previous active rubric.
    existing = db.scalars(
        select(Rubric).where(
            Rubric.event_id == payload.event_id
        )
    ).all()

    for old_rubric in existing:
        old_rubric.active = False

    rubric = Rubric(
        event_id=payload.event_id,
        name=payload.name.strip(),
        active=True,
    )

    db.add(rubric)
    db.flush()

    for item in payload.criteria:
        db.add(
            Criterion(
                rubric_id=rubric.id,
                name=item.name.strip(),
                weight=item.weight,
                max_score=item.max_score,
            )
        )

    db.commit()

    write_audit(
        db,
        user.id,
        "rubric.create",
        "rubric",
        rubric.id,
        {
            "event_id": payload.event_id,
            "criteria_count": len(
                payload.criteria
            ),
        },
    )

    db.commit()

    created = get_rubric(
        db,
        rubric.id,
    )

    if not created:
        raise HTTPException(
            status_code=500,
            detail="Failed to create rubric",
        )

    return created


@router.get(
    "/api/rubrics/{rubric_id}",
    response_model=RubricOut,
)
def get_rubric_endpoint(
    rubric_id: int,
    db: Session = Depends(get_db),
):
    rubric = get_rubric(
        db,
        rubric_id,
    )

    if not rubric:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rubric not found",
        )

    return rubric


@router.put(
    "/api/rubrics/{rubric_id}",
    response_model=RubricOut,
)
def replace_rubric(
    rubric_id: int,
    payload: RubricCreate,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(
            UserRole.ORGANIZER,
            UserRole.ADMIN,
        )
    ),
):
    rubric = get_rubric(
        db,
        rubric_id,
    )

    if not rubric:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rubric not found",
        )

    if rubric.event_id != payload.event_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rubric event cannot be changed",
        )

    # Once scoring has started, don't destroy
    # the criteria that existing scores reference.
    score_count = db.scalar(
        select(func.count(Score.id))
        .join(
            Criterion,
            Criterion.id == Score.criterion_id,
        )
        .where(
            Criterion.rubric_id == rubric.id
        )
    ) or 0

    if score_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Rubric cannot be modified after "
                "judging has started"
            ),
        )

    rubric.name = payload.name.strip()

    for criterion in list(
        rubric.criteria
    ):
        db.delete(criterion)

    db.flush()

    for item in payload.criteria:
        db.add(
            Criterion(
                rubric_id=rubric.id,
                name=item.name.strip(),
                weight=item.weight,
                max_score=item.max_score,
            )
        )

    rubric.active = True

    db.commit()

    write_audit(
        db,
        user.id,
        "rubric.update",
        "rubric",
        rubric.id,
    )

    db.commit()

    updated = get_rubric(
        db,
        rubric.id,
    )

    return updated


# =========================================================
# ACTIVE RUBRIC BY EVENT
# =========================================================

@router.get(
    "/api/rubrics/active",
    response_model=RubricOut,
)
def get_active_rubric_endpoint(
    event_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(
            UserRole.JUDGE,
            UserRole.ORGANIZER,
            UserRole.ADMIN,
        )
    ),
):
    rubric = get_active_rubric(db, event_id)
    if not rubric:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active rubric not found",
        )
    return rubric


# =========================================================
# JUDGE ASSIGNMENTS
# =========================================================

@router.get(
    "/api/judge/assignments",
)
def my_assignments(
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(
            UserRole.JUDGE,
        )
    ),
):
    judge = get_judge_for_user(
        db,
        user.id,
    )

    assignments = db.scalars(
        select(JudgeAssignment)
        .options(
            joinedload(
                JudgeAssignment.project
            )
        )
        .where(
            JudgeAssignment.judge_id
            == judge.id
        )
        .order_by(
            JudgeAssignment.id
        )
    ).all()

    output = []

    for assignment in assignments:

        project = assignment.project

        rubric = get_active_rubric(
            db,
            project.event_id,
        )

        criteria_count = (
            len(rubric.criteria)
            if rubric
            else 0
        )

        scored_count = db.scalar(
            select(func.count(Score.id))
            .where(
                Score.judge_id == judge.id,
                Score.project_id == project.id,
            )
        ) or 0

        output.append(
            {
                "project_id": project.id,
                "title": project.title,
                "status": project.status.value,
                "completed": (
                    criteria_count > 0
                    and scored_count
                    == criteria_count
                ),
                "scores_completed": scored_count,
                "scores_required": criteria_count,
            }
        )

    return output


# =========================================================
# SUBMIT / UPDATE EVALUATION
# =========================================================

@router.post(
    "/api/judge/scores",
    response_model=EvaluationOut,
)
def submit_evaluation(
    payload: EvaluationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(
            UserRole.JUDGE,
            UserRole.ADMIN,
        )
    ),
):
    judge = get_judge_for_user(
        db,
        user.id,
    )

    project = db.get(
        Project,
        payload.project_id,
    )

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if project.status != ProjectStatus.SUBMITTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only submitted projects can be judged",
        )

    # Judge must actually be assigned.
    assignment = db.scalar(
        select(JudgeAssignment).where(
            JudgeAssignment.judge_id
            == judge.id,
            JudgeAssignment.project_id
            == project.id,
        )
    )

    if not assignment and user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Project is not assigned to you",
        )

    rubric = get_active_rubric(
        db,
        project.event_id,
    )

    if not rubric:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active rubric configured",
        )

    criteria = {
        criterion.id: criterion
        for criterion in rubric.criteria
    }

    submitted_ids = [
        item.criterion_id
        for item in payload.scores
    ]

    # Reject duplicate criterion entries.
    if len(submitted_ids) != len(
        set(submitted_ids)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A criterion cannot be scored more than once",
        )

    if set(submitted_ids) != set(
        criteria.keys()
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Every active rubric criterion "
                "must be scored exactly once"
            ),
        )

    # Validate score range.
    for item in payload.scores:

        criterion = criteria[
            item.criterion_id
        ]

        if (
            item.score < 0
            or item.score > criterion.max_score
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Score for '{criterion.name}' "
                    f"must be between 0 and "
                    f"{criterion.max_score}"
                ),
            )

    # Upsert scores.
    for item in payload.scores:

        existing = db.scalar(
            select(Score).where(
                Score.judge_id == judge.id,
                Score.project_id
                == project.id,
                Score.criterion_id
                == item.criterion_id,
            )
        )

        if existing:

            existing.score = item.score
            existing.comment = item.comment

        else:

            db.add(
                Score(
                    judge_id=judge.id,
                    project_id=project.id,
                    criterion_id=item.criterion_id,
                    score=item.score,
                    comment=item.comment,
                )
            )

    db.flush()

    scores = db.scalars(
        select(Score).where(
            Score.judge_id == judge.id,
            Score.project_id == project.id,
        )
        .order_by(
            Score.criterion_id
        )
    ).all()

    write_audit(
        db,
        user.id,
        "judge.score.submit",
        "project",
        project.id,
        {
            "judge_id": judge.id,
            "rubric_id": rubric.id,
        },
    )

    db.commit()
    dispatch_webhook(db, project.event_id, "judge.score.submit", {"project_id": project.id, "judge_id": judge.id, "rubric_id": rubric.id})

    return evaluation_response(
        project.id,
        judge.id,
        scores,
        criteria,
    )


# =========================================================
# CURRENT JUDGE'S OWN SCORES
# =========================================================

@router.get(
    "/api/judge/scores",
    response_model=list[EvaluationOut],
)
def get_my_scores(
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(
            UserRole.JUDGE,
        )
    ),
):
    judge = get_judge_for_user(
        db,
        user.id,
    )

    scores = db.scalars(
        select(Score)
        .where(
            Score.judge_id == judge.id
        )
        .order_by(
            Score.project_id,
            Score.criterion_id,
        )
    ).all()

    grouped = defaultdict(list)

    for score in scores:
        grouped[
            score.project_id
        ].append(score)

    output = []

    for project_id, project_scores in grouped.items():

        project = db.get(
            Project,
            project_id,
        )

        if not project:
            continue

        rubric = get_active_rubric(
            db,
            project.event_id,
        )

        if not rubric:
            continue

        criteria = {
            criterion.id: criterion
            for criterion in rubric.criteria
        }

        output.append(
            evaluation_response(
                project_id,
                judge.id,
                project_scores,
                criteria,
            )
        )

    return output


# =========================================================
# ORGANIZER / ADMIN SCORE ACCESS
# =========================================================

@router.get(
    "/api/judge/scores/{judge_id}",
    response_model=list[EvaluationOut],
)
def get_judge_scores(
    judge_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(
            UserRole.ORGANIZER,
            UserRole.ADMIN,
        )
    ),
):
    target_judge = db.get(
        Judge,
        judge_id,
    )

    if not target_judge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Judge not found",
        )

    scores = db.scalars(
        select(Score)
        .where(
            Score.judge_id
            == judge_id
        )
        .order_by(
            Score.project_id,
            Score.criterion_id,
        )
    ).all()

    grouped = defaultdict(list)

    for score in scores:
        grouped[
            score.project_id
        ].append(score)

    output = []

    for project_id, project_scores in grouped.items():

        project = db.get(
            Project,
            project_id,
        )

        if not project:
            continue

        rubric = get_active_rubric(
            db,
            project.event_id,
        )

        if not rubric:
            continue

        criteria = {
            criterion.id: criterion
            for criterion in rubric.criteria
        }

        output.append(
            evaluation_response(
                project_id,
                judge_id,
                project_scores,
                criteria,
            )
        )

    return output


# =========================================================
# JUDGE PROGRESS
# =========================================================

@router.get(
    "/api/judge/progress",
    response_model=list[ProgressOut],
)
def judge_progress(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role == UserRole.JUDGE:
        current_judge = get_judge_for_user(db, user.id)
        judges = [current_judge]
    elif user.role in {UserRole.ORGANIZER, UserRole.ADMIN}:
        judges = db.scalars(
            select(Judge)
            .options(joinedload(Judge.user))
            .order_by(Judge.id)
        ).all()
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot view judge progress",
        )

    output = []

    for judge in judges:

        assignments = db.scalars(
            select(JudgeAssignment).where(
                JudgeAssignment.judge_id
                == judge.id
            )
        ).all()

        assigned = len(assignments)
        completed = 0

        for assignment in assignments:

            rubric = get_active_rubric(
                db,
                assignment.project.event_id,
            )

            if not rubric:
                continue

            criteria_count = len(
                rubric.criteria
            )

            scored_count = db.scalar(
                select(func.count(Score.id))
                .where(
                    Score.judge_id == judge.id,
                    Score.project_id
                    == assignment.project_id,
                )
            ) or 0

            if (
                criteria_count > 0
                and scored_count
                == criteria_count
            ):
                completed += 1

        pending = assigned - completed

        percentage = (
            round(
                completed
                / assigned
                * 100,
                2,
            )
            if assigned
            else 0.0
        )

        output.append(
            ProgressOut(
                judge_id=judge.id,
                name=judge.user.name,
                assigned=assigned,
                completed=completed,
                pending=pending,
                completion_percent=percentage,
            )
        )

    return output


# =========================================================
# AUDIT LOGS
# =========================================================

@router.get(
    "/api/audit",
)
def audit_logs(
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(
            UserRole.ORGANIZER,
            UserRole.ADMIN,
        )
    ),
):
    from app.db.models.audit import AuditLog

    logs = db.scalars(
        select(AuditLog)
        .order_by(
            AuditLog.id.desc()
        )
        .limit(250)
    ).all()

    return [
        {
            "id": log.id,
            "actor_user_id": log.actor_user_id,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "details": log.details,
            "created_at": log.created_at,
        }
        for log in logs
    ]