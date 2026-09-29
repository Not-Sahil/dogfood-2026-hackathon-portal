from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.dependencies import get_current_user, require_roles
from app.db.database import get_db
from app.db.models.judge import Judge, JudgeAssignment
from app.db.models.platform import PairwiseComparison
from app.db.models.project import Project, ProjectStatus
from app.db.models.user import User, UserRole
from app.schemas.platform import PairwiseVoteIn
from app.services.audit import write_audit
from app.services.pairwise import bradley_terry_rankings
from app.services.webhooks import dispatch_webhook

router = APIRouter(prefix="/api/pairwise", tags=["Pairwise Judging"])


def _judge(db: Session, user: User) -> Judge:
    judge = db.scalar(select(Judge).where(Judge.user_id == user.id))
    if not judge:
        raise HTTPException(404, "Judge profile not found")
    return judge


@router.get("/next")
def next_pair(event_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.JUDGE, UserRole.ADMIN))):
    judge = _judge(db, user)
    projects = db.scalars(select(Project).where(Project.event_id == event_id, Project.status == ProjectStatus.SUBMITTED).join(JudgeAssignment, JudgeAssignment.project_id == Project.id).where(JudgeAssignment.judge_id == judge.id)).all()
    projects = sorted({p.id: p for p in projects}.values(), key=lambda p: p.id)
    comparisons = db.scalars(select(PairwiseComparison).where(PairwiseComparison.event_id == event_id, PairwiseComparison.judge_id == judge.id)).all()
    done = {(min(c.project_low_id, c.project_high_id), max(c.project_low_id, c.project_high_id)) for c in comparisons}
    for i, a in enumerate(projects):
        for b in projects[i + 1:]:
            key = (min(a.id, b.id), max(a.id, b.id))
            if key not in done:
                return {"event_id": event_id, "project_a": {"id": a.id, "title": a.title, "summary": a.summary}, "project_b": {"id": b.id, "title": b.title, "summary": b.summary}}
    raise HTTPException(404, "No unreviewed pair remains for this judge")


@router.post("/vote")
def vote(payload: PairwiseVoteIn, db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.JUDGE, UserRole.ADMIN))):
    if payload.project_a_id == payload.project_b_id:
        raise HTTPException(400, "Projects must be different")
    if payload.winner_id not in {payload.project_a_id, payload.project_b_id}:
        raise HTTPException(400, "Winner must be one of the two projects")
    judge = _judge(db, user)
    projects = {p.id: p for p in db.scalars(select(Project).where(Project.id.in_([payload.project_a_id, payload.project_b_id]), Project.event_id == payload.event_id, Project.status == ProjectStatus.SUBMITTED)).all()}
    if len(projects) != 2:
        raise HTTPException(404, "Both projects must be submitted in the selected event")
    assigned = {p_id for p_id in [payload.project_a_id, payload.project_b_id] if db.scalar(select(JudgeAssignment).where(JudgeAssignment.judge_id == judge.id, JudgeAssignment.project_id == p_id))}
    if len(assigned) != 2 and user.role != UserRole.ADMIN:
        raise HTTPException(403, "Pairwise mode only includes projects assigned to you")
    low, high = sorted([payload.project_a_id, payload.project_b_id])
    existing = db.scalar(select(PairwiseComparison).where(PairwiseComparison.event_id == payload.event_id, PairwiseComparison.judge_id == judge.id, PairwiseComparison.project_low_id == low, PairwiseComparison.project_high_id == high))
    if existing:
        raise HTTPException(409, "This pair has already been compared")
    row = PairwiseComparison(event_id=payload.event_id, judge_id=judge.id, project_low_id=low, project_high_id=high, winner_id=payload.winner_id)
    db.add(row)
    db.commit()
    write_audit(db, user.id, "pairwise.vote", "event", payload.event_id, {"project_a": payload.project_a_id, "project_b": payload.project_b_id, "winner": payload.winner_id})
    db.commit()
    dispatch_webhook(db, payload.event_id, "pairwise.vote", {"project_a": payload.project_a_id, "project_b": payload.project_b_id, "winner": payload.winner_id})
    return {"message": "Pairwise preference recorded"}


@router.get("/ranking")
def ranking(event_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.ORGANIZER, UserRole.ADMIN))):
    rows = db.scalars(select(PairwiseComparison).where(PairwiseComparison.event_id == event_id)).all()
    comparisons = [(r.project_low_id, r.project_high_id, r.winner_id) for r in rows]
    ranked = bradley_terry_rankings(comparisons)
    titles = {p.id: p.title for p in db.scalars(select(Project).where(Project.event_id == event_id)).all()}
    for item in ranked:
        item["project_title"] = titles.get(item["project_id"], "Project")
    return {"event_id": event_id, "method": "Bradley-Terry MM", "comparisons": len(rows), "rankings": ranked}
