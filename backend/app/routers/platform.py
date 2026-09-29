import csv
import io
import json

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.dependencies import require_roles
from app.core.time import ensure_utc, utcnow
from app.db.database import get_db
from app.db.models.event import Event
from app.db.models.judge import Judge, JudgeAssignment
from app.db.models.platform import JudgeRecord, WebhookEndpoint
from app.db.models.project import Project, ProjectStatus
from app.db.models.team import Team, TeamMember
from app.db.models.user import User, UserRole
from app.schemas.platform import BulkImportResult, WebhookCreate, WebhookOut
from app.services.audit import write_audit
from app.services.records import sign_record, signing_public_key_b64, verify_record

router = APIRouter(prefix="/api", tags=["Platform"])


@router.get("/system/export/projects.csv")
def export_projects(
    event_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ORGANIZER, UserRole.ADMIN)),
):
    query = select(Project).options(joinedload(Project.team), joinedload(Project.track)).order_by(Project.id)
    if event_id is not None:
        query = query.where(Project.event_id == event_id)
    projects = db.scalars(query).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "event_id", "team_id", "track_id", "title", "summary", "repo_url", "demo_url", "status"])
    for p in projects:
        writer.writerow([p.id, p.event_id, p.team_id, p.track_id, p.title, p.summary, p.repo_url or "", p.demo_url or "", p.status.value])
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=projects-export.csv"})


@router.post("/system/import/teams.csv", response_model=BulkImportResult)
async def import_teams(
    event_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ORGANIZER, UserRole.ADMIN)),
):
    if not db.get(Event, event_id):
        raise HTTPException(404, "Event not found")
    data = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(data))
    imported = skipped = 0
    errors: list[str] = []
    for line_no, row in enumerate(reader, start=2):
        name = (row.get("name") or row.get("team_name") or "").strip()
        email = (row.get("participant_email") or row.get("email") or "").strip().lower()
        if not name or not email:
            skipped += 1
            errors.append(f"line {line_no}: name and participant_email are required")
            continue
        participant = db.scalar(select(User).where(User.email == email))
        if not participant:
            skipped += 1
            errors.append(f"line {line_no}: participant account {email} does not exist")
            continue
        existing = db.scalar(select(Team).where(Team.event_id == event_id, Team.name == name))
        if existing:
            skipped += 1
            continue
        team = Team(event_id=event_id, name=name, created_by=participant.id)
        db.add(team)
        db.flush()
        db.add(TeamMember(team_id=team.id, user_id=participant.id, is_captain=True))
        imported += 1
    db.commit()
    write_audit(db, user.id, "bulk.import.teams", "event", event_id, {"imported": imported, "skipped": skipped})
    db.commit()
    return BulkImportResult(imported=imported, skipped=skipped, errors=errors[:50])


@router.post("/webhooks", response_model=WebhookOut)
def create_webhook(payload: WebhookCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.ORGANIZER, UserRole.ADMIN))):
    if payload.event_id is not None and not db.get(Event, payload.event_id):
        raise HTTPException(404, "Event not found")
    url = payload.url.strip()
    if not url.lower().startswith(("http://", "https://")):
        raise HTTPException(400, "Webhook URL must use http:// or https://")
    row = WebhookEndpoint(event_id=payload.event_id, url=url, secret=payload.secret)
    db.add(row)
    db.commit()
    db.refresh(row)
    write_audit(db, user.id, "webhook.create", "webhook", row.id)
    db.commit()
    return row


@router.get("/webhooks", response_model=list[WebhookOut])
def list_webhooks(db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.ORGANIZER, UserRole.ADMIN))):
    return db.scalars(select(WebhookEndpoint).order_by(WebhookEndpoint.id.desc())).all()


@router.delete("/webhooks/{webhook_id}")
def delete_webhook(webhook_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.ORGANIZER, UserRole.ADMIN))):
    row = db.get(WebhookEndpoint, webhook_id)
    if not row:
        raise HTTPException(404, "Webhook not found")
    db.delete(row)
    db.commit()
    write_audit(db, user.id, "webhook.delete", "webhook", webhook_id)
    db.commit()
    return {"message": "Webhook deleted"}


@router.get("/embed/gallery", response_class=HTMLResponse)
def embed_gallery(event_id: int, db: Session = Depends(get_db)):
    projects = db.scalars(select(Project).where(Project.event_id == event_id, Project.status == ProjectStatus.SUBMITTED).order_by(Project.id)).all()
    cards = "".join(f'<article><span>PROJECT {p.id:02d}</span><h3>{p.title}</h3><p>{p.summary}</p></article>' for p in projects[:50])
    html = f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{{margin:0;background:#08101f;color:#eef3ff;font:14px system-ui,sans-serif;padding:18px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}}article{{border:1px solid #25304b;border-radius:14px;padding:16px;background:#0d1628}}span{{font:10px ui-monospace;color:#59f5d1;letter-spacing:.12em}}h3{{margin:9px 0 6px}}p{{margin:0;color:#8e9ab3;line-height:1.6}}</style></head><body><div class="grid">{cards or '<p>No submitted projects.</p>'}</div></body></html>'''
    return HTMLResponse(html)


@router.get("/judge-records/public-key")
def judge_record_public_key():
    return {"algorithm": "Ed25519", "public_key": signing_public_key_b64()}


@router.get("/judge-records/{judge_id}")
def judge_record(judge_id: int, event_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.ORGANIZER, UserRole.ADMIN))):
    judge = db.scalar(select(Judge).options(joinedload(Judge.user)).where(Judge.id == judge_id))
    if not judge:
        raise HTTPException(404, "Judge not found")
    assigned = db.scalar(select(func.count(JudgeAssignment.id)).where(JudgeAssignment.judge_id == judge_id)) or 0
    payload = {
        "record_type": "judge_participation",
        "judge_id": judge_id,
        "judge_name": judge.user.name,
        "event_id": event_id,
        "assigned_reviews": int(assigned),
        "generated_at": utcnow().isoformat(),
    }
    signature = sign_record(payload)
    existing = db.scalar(select(JudgeRecord).where(JudgeRecord.judge_id == judge_id, JudgeRecord.event_id == event_id))
    if not existing:
        existing = JudgeRecord(judge_id=judge_id, event_id=event_id, payload_json=json.dumps(payload, sort_keys=True, separators=(",", ":")), signature=signature)
        db.add(existing)
    else:
        existing.payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        existing.signature = signature
    db.commit()
    return {"record_id": existing.id, "record": payload, "signature": signature, "public_key": signing_public_key_b64(), "verified": verify_record(payload, signature)}


@router.post("/judge-records/verify")
def verify_judge_record(payload: dict):
    signature = payload.pop("signature", None)
    if not signature:
        raise HTTPException(400, "signature is required")
    return {"valid": verify_record(payload, signature), "algorithm": "Ed25519", "public_key": signing_public_key_b64()}


@router.get("/judge-records/{judge_id}/certificate", response_class=HTMLResponse)
def judge_certificate(judge_id: int, event_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.ORGANIZER, UserRole.ADMIN))):
    result = judge_record(judge_id, event_id, db, user)
    record = result["record"]
    html = f'''<!doctype html><html><head><meta charset="utf-8"><style>body{{font-family:Georgia,serif;background:#101826;color:#f6f7fb;display:grid;place-items:center;min-height:100vh}}main{{width:min(820px,88vw);border:1px solid #3ee7c0;padding:52px;text-align:center;background:#111c30}}small{{letter-spacing:.18em;color:#59f5d1}}h1{{font-size:46px;margin:22px 0 8px}}p{{color:#a9b5ca}}.sig{{font:11px ui-monospace;word-break:break-all;margin-top:28px}}</style></head><body><main><small>DOGFOOD 2026 · JUDGE RECORD</small><h1>Certificate of Participation</h1><p>This certifies that <strong>{record['judge_name']}</strong> participated as a judge for event #{record['event_id']} and completed an auditable judge record.</p><p>Assigned reviews: <strong>{record['assigned_reviews']}</strong></p><div class="sig">Ed25519 signature: {result['signature']}</div></main></body></html>'''
    return HTMLResponse(html)

@router.get("/normalization/proof")
def normalization_proof(event_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.ORGANIZER, UserRole.ADMIN))):
    from app.services.results import build_results
    result = build_results(db, event_id)
    changed = [
        {
            "project_id": row["project_id"],
            "project_title": row["project_title"],
            "raw_score": row["raw_score"],
            "normalized_score": row["normalized_score"],
            "rank_raw": row["rank_raw"],
            "rank_normalized": row["rank_normalized"],
            "rank_change": row["rank_change"],
        }
        for row in result["rows"]
        if row["rank_change"] not in (None, 0) or row["normalized_score"] != row["raw_score"]
    ]
    return {"event_id": event_id, "method": result["normalization"], "changes": changed, "integrity": result["integrity"]}


@router.get("/integrity/duplicates")
def duplicate_scan(event_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.ORGANIZER, UserRole.ADMIN))):
    from app.services.duplicates import find_duplicate_groups
    projects = db.scalars(select(Project).where(Project.event_id == event_id, Project.status == ProjectStatus.SUBMITTED).order_by(Project.id)).all()
    groups = find_duplicate_groups(projects)
    write_audit(db, user.id, "integrity.duplicate_scan", "event", event_id, {"groups": len(groups)})
    db.commit()
    return {"event_id": event_id, "groups": groups}


@router.get("/public/judge-records/{record_id}")
def public_judge_record(record_id: int, db: Session = Depends(get_db)):
    row = db.get(JudgeRecord, record_id)
    if not row:
        raise HTTPException(404, "Judge record not found")
    record = json.loads(row.payload_json)
    return {"record": record, "signature": row.signature, "public_key": signing_public_key_b64(), "verified": verify_record(record, row.signature)}
