import hashlib
import hmac
from collections import defaultdict
from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.dependencies import get_current_user, require_roles
from app.core.time import ensure_utc, utcnow
from app.db.database import get_db
from app.db.models.audit import AuditLog
from app.db.models.platform import CommunityComment, CommunityVote, CommunityVoteConfig
from app.db.models.project import Project, ProjectStatus
from app.db.models.user import User, UserRole
from app.schemas.platform import CommunityCommentIn, CommunityConfigIn, CommunityConfigOut, CommunityVoteIn
from app.services.audit import write_audit
from app.services.webhooks import dispatch_webhook

router = APIRouter(prefix="/api/community", tags=["Community"])


def _config(db: Session, event_id: int) -> CommunityVoteConfig:
    cfg = db.scalar(select(CommunityVoteConfig).where(CommunityVoteConfig.event_id == event_id))
    if not cfg:
        raise HTTPException(404, "Community voting is not configured for this event")
    return cfg


def _open(cfg: CommunityVoteConfig) -> bool:
    now = utcnow()
    return ensure_utc(cfg.voting_start) <= now <= ensure_utc(cfg.voting_end)


def _project(db: Session, event_id: int, project_id: int) -> Project:
    project = db.scalar(select(Project).where(Project.id == project_id, Project.event_id == event_id, Project.status == ProjectStatus.SUBMITTED))
    if not project:
        raise HTTPException(404, "Submitted project not found")
    return project


@router.get("/config", response_model=CommunityConfigOut)
def get_config(event_id: int, db: Session = Depends(get_db)):
    return _config(db, event_id)


@router.post("/config", response_model=CommunityConfigOut)
def create_or_update_config(
    payload: CommunityConfigIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ORGANIZER, UserRole.ADMIN)),
):
    from app.db.models.event import Event
    if not db.get(Event, payload.event_id):
        raise HTTPException(404, "Event not found")

    start = ensure_utc(payload.voting_start)
    end = ensure_utc(payload.voting_end)
    if start >= end:
        raise HTTPException(400, "Voting start must be before voting end")
    cfg = db.scalar(select(CommunityVoteConfig).where(CommunityVoteConfig.event_id == payload.event_id))
    if not cfg:
        cfg = CommunityVoteConfig(event_id=payload.event_id)
        db.add(cfg)
    cfg.voting_start = start
    cfg.voting_end = end
    cfg.results_hidden_until_close = payload.results_hidden_until_close
    cfg.max_votes_per_user = payload.max_votes_per_user
    cfg.active = payload.active
    db.commit()
    db.refresh(cfg)
    write_audit(db, user.id, "community.config.save", "event", payload.event_id)
    db.commit()
    return cfg


@router.get("/projects")
def community_projects(event_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cfg = _config(db, event_id)
    projects = db.scalars(select(Project).options(joinedload(Project.team), joinedload(Project.track)).where(Project.event_id == event_id, Project.status == ProjectStatus.SUBMITTED)).all()
    # Deterministic per-user shuffle prevents users from comparing a fixed first-page ordering.
    key = str(user.id).encode()
    projects.sort(key=lambda p: hmac.new(key, f"{event_id}:{p.id}".encode(), hashlib.sha256).hexdigest())
    return [
        {
            "id": p.id,
            "title": p.title,
            "summary": p.summary,
            "team_name": p.team.name if p.team else None,
            "track_name": p.track.name if p.track else None,
            "repo_url": p.repo_url,
            "demo_url": p.demo_url,
            "voting_open": cfg.active and _open(cfg),
        }
        for p in projects
    ]


@router.post("/vote", status_code=status.HTTP_201_CREATED)
def cast_vote(payload: CommunityVoteIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.PARTICIPANT))):
    cfg = _config(db, payload.event_id)
    if not cfg.active or not _open(cfg):
        raise HTTPException(403, "Community voting is closed")
    _project(db, payload.event_id, payload.project_id)
    count = db.scalar(select(func.count(CommunityVote.id)).where(CommunityVote.event_id == payload.event_id, CommunityVote.voter_user_id == user.id)) or 0
    if count >= cfg.max_votes_per_user:
        raise HTTPException(429, "Your voting allowance for this event has been reached")
    ip = request.client.host if request.client else "unknown"
    ip_hash = hashlib.sha256(ip.encode()).hexdigest()
    recent = db.scalar(select(func.count(CommunityVote.id)).where(CommunityVote.event_id == payload.event_id, CommunityVote.voter_ip_hash == ip_hash, CommunityVote.created_at >= utcnow().replace(second=0, microsecond=0))) or 0
    if recent >= 20:
        raise HTTPException(429, "Too many votes from this address in the current minute")
    vote = CommunityVote(event_id=payload.event_id, voter_user_id=user.id, project_id=payload.project_id, voter_ip_hash=ip_hash)
    db.add(vote)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "You have already voted for this project") from exc
    write_audit(db, user.id, "community.vote.cast", "project", payload.project_id, {"event_id": payload.event_id})
    db.commit()
    dispatch_webhook(db, payload.event_id, "community.vote.cast", {"project_id": payload.project_id, "voter_id": user.id})
    return {"message": "Vote recorded", "project_id": payload.project_id}


@router.post("/comments", status_code=status.HTTP_201_CREATED)
def add_comment(payload: CommunityCommentIn, db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.PARTICIPANT))):
    cfg = _config(db, payload.event_id)
    if not cfg.active or not _open(cfg):
        raise HTTPException(403, "Community discussion is closed")
    _project(db, payload.event_id, payload.project_id)
    comment = CommunityComment(event_id=payload.event_id, project_id=payload.project_id, author_user_id=user.id, body=payload.body.strip())
    db.add(comment)
    db.commit()
    db.refresh(comment)
    write_audit(db, user.id, "community.comment.create", "project", payload.project_id, {"event_id": payload.event_id})
    db.commit()
    dispatch_webhook(db, payload.event_id, "community.comment.create", {"project_id": payload.project_id})
    return {"id": comment.id, "project_id": comment.project_id, "body": comment.body, "created_at": comment.created_at, "author": user.name}


@router.get("/comments")
def list_comments(project_id: int, event_id: int, db: Session = Depends(get_db)):
    _project(db, event_id, project_id)
    rows = db.scalars(select(CommunityComment).options(joinedload(CommunityComment.author)).where(CommunityComment.event_id == event_id, CommunityComment.project_id == project_id).order_by(CommunityComment.created_at.desc())).all()
    return [{"id": r.id, "body": r.body, "author": r.author.name, "created_at": r.created_at} for r in rows]


@router.get("/results")
def community_results(event_id: int, db: Session = Depends(get_db)):
    cfg = _config(db, event_id)
    if cfg.results_hidden_until_close and utcnow() < ensure_utc(cfg.voting_end):
        raise HTTPException(403, "Community results are hidden until voting closes")
    rows = db.execute(select(CommunityVote.project_id, func.count(CommunityVote.id).label("votes")).where(CommunityVote.event_id == event_id).group_by(CommunityVote.project_id).order_by(func.count(CommunityVote.id).desc())).all()
    return [{"project_id": project_id, "votes": votes, "rank": idx + 1} for idx, (project_id, votes) in enumerate(rows)]
