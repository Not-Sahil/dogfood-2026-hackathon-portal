import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.dependencies import require_roles
from app.db.database import get_db
from app.db.models.user import User, UserRole
from app.schemas.result import ResultResponse, ResultRow
from app.services.results import build_results

router = APIRouter(prefix="/api", tags=["Results"])


@router.get("/results", response_model=ResultResponse)
def results(
    event_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ORGANIZER, UserRole.ADMIN)),
):
    try:
        return build_results(db, event_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/results/{project_id}", response_model=ResultRow)
def project_explanation(
    project_id: int,
    event_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ORGANIZER, UserRole.ADMIN)),
):
    try:
        result = build_results(db, event_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    for row in result["rows"]:
        if row["project_id"] == project_id:
            return row

    raise HTTPException(
        status_code=404,
        detail=f"Project {project_id} is not present in event {event_id} results",
    )


@router.get("/export.csv")
def export_csv(
    event_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ORGANIZER, UserRole.ADMIN)),
):
    try:
        result = build_results(db, event_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "rank_raw",
            "rank_normalized",
            "project_id",
            "project_title",
            "team_name",
            "track_name",
            "raw_score",
            "normalized_score",
            "completed_reviews",
            "assigned_reviews",
            "rank_change",
            "normalization_method",
            "normalization_scale",
        ]
    )

    normalization = result["normalization"]
    for row in result["rows"]:
        writer.writerow(
            [
                row["rank_raw"],
                row["rank_normalized"],
                row["project_id"],
                row["project_title"],
                row.get("team_name"),
                row.get("track_name"),
                row["raw_score"],
                row["normalized_score"],
                row["completed_reviews"],
                row["assigned_reviews"],
                row["rank_change"],
                normalization["method"],
                normalization["scale"],
            ]
        )

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f"attachment; filename=dogfood-results-event-{event_id}.csv"
            )
        },
    )
